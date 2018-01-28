import os
import time
import re
from slackclient import SlackClient
import config
from task_manager import TaskList, TaskManager, Status

# instantiate Slack client
slack_client = SlackClient(config.auth["bot_access_token"])
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None
taskmanager = TaskManager()

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "do"
MENTION_REGEX = "^<@(|[WU].+)>(.*)"

kPublishToChannel = "random"

class Bot:
    def __init__(self):
        self.user_list = {}
        self.conversations = {}
        self.channels = {}

    def mainloop(self):
        if slack_client.rtm_connect(with_team_state=False):
            print("Starter Bot connected and running!")
            # Read bot's user ID by calling Web API method `auth.test`
            starterbot_id = slack_client.api_call("auth.test")["user_id"]
            users = slack_client.api_call("users.list")["members"]
            channels = slack_client.api_call("channels.list")["channels"]

            for user in users:
                self.user_list[user["id"]] = user

            for channel in channels:
                self.channels[channel["name"]] = channel["id"]

            while True:
                try:
                    command, channel = self.parse_bot_commands(slack_client.rtm_read())
                    if command:
                        self.handle_command(command, channel)
                except Exception as e:
                    print(e)

                #time.sleep(RTM_READ_DELAY)
        else:
            print("Connection failed. Exception traceback printed above.")

    def parse_bot_commands(self, slack_events):
        """
            Parses a list of events coming from the Slack RTM API to find bot commands.
            If a bot command is found, this function returns a tuple of command and channel.
            If its not found, then this function returns None, None.
        """
        # print(slack_events)
        for event in slack_events:
            if event["type"] == "message" and not "subtype" in event:
                if event["channel"].startswith("D"):
                    self.handle_dm_command(event["user"], event["text"], event["channel"])
                # user_id, message = self.parse_direct_mention(event["text"])
                # if user_id == starterbot_id:
                #     return message, event["channel"]
        return None, None

    def handle_dm_command(self, from_user, text, channel):
        print ("Text: {} from user: {}".format(text, from_user))
        if from_user not in self.conversations:
            self.conversations[from_user] = Conversation(from_user, channel,
                                                         self.user_list[from_user]["real_name"],
                                                         self.user_list[from_user]["profile"]["image_48"])

        self.conversations[from_user].incoming_message(text)



    def parse_direct_mention(self, message_text):
        """
            Finds a direct mention (a mention that is at the beginning) in message text
            and returns the user ID which was mentioned. If there is no direct mention, returns None
        """
        matches = re.search(MENTION_REGEX, message_text)
        # the first group contains the username, the second group contains the remaining message
        return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

    def handle_command(self, command, channel):
        """
            Executes bot command if the command is known
        """
        print ("command : {}, channel: {}".format(command, channel))
        # Default response is help text for the user
        default_response = "Not sure what you mean. Try *{}*.".format(EXAMPLE_COMMAND)

        # Finds and executes the given command, filling in response
        response =  ":white_check_mark: Make awesome bot \n :white_medium_square: make car autonomous"
        # This is where you start to implement more commands!
        if command.startswith(EXAMPLE_COMMAND):
            response = "Sure...write some more code then I can do that!"

        # Sends the response back to the channel
        slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            username="Faraz's Standup Report",
            text=response or default_response
        )

class Conversation:
    WaitingForStart, WaitingForCommands = range(2)

    def __init__(self, uid, userid, name, icon_url):
        self.current_status = self.WaitingForStart
        self.uid = uid
        self.userid = userid
        self.name = name
        self.icon_url = icon_url
        self.task_list = taskmanager.get_tasklist(uid)
        self.new_tasks = []
        self.updated_tasks = set()
        self.main_task_list_ts = None

    def incoming_message(self, message):
        msg = message.lower()

        if self.current_status == self.WaitingForStart:
            if msg.startswith("start"):
                self.send_response("_Lets begin!_\n")
                self.show_help()
                response = self.show_task_list()
                self.main_task_list_ts = response["ts"]
                self.current_status = self.WaitingForCommands
            else:
                self.send_response("_Type `start` to begin_")

        elif self.current_status == self.WaitingForCommands:
            if msg.startswith("done"):
                self.check_and_mark_status(Status.DONE, msg, "Great job getting those done! :clap:\n")
                self.show_task_list(update=True)
            elif msg.startswith("wip"):
                self.check_and_mark_status(Status.WIP, msg, "Its okay we'll get those tomorrow! :punch:\n")
                self.show_task_list(update=True)
            elif msg.startswith("cancelled"):
                self.check_and_mark_status(Status.CANCELLED, msg, "They weren't worth it anyways.. \n")
                self.show_task_list(update=True)
            elif msg.startswith("publish"):
                self.publish()
                self.current_status = self.WaitingForStart

            elif msg.startswith("-"):
                lines = msg.strip().split("\n")
                for line in lines:
                    split = line.strip().split("-")
                    if len(split) > 1:
                        new_task = self.add_task(split[1].strip());
                        self.new_tasks.append(new_task)
                        self.updated_tasks.add(new_task)

                self.show_task_list(update=True)
            else:
                self.show_help(error=True)


    def check_and_mark_status(self, status, msg, success_msg):
        task_ids = self.get_task_ids(msg)
        if task_ids:
            self.send_response(success_msg)
            self.mark_status(status, task_ids)
            self.updated_tasks.update(task_ids)
            print(self.updated_tasks)
        else:
            self.show_help(error=True)

    def show_help(self, error=False):
        if error:
            self.send_response("I don't understand what you mean :confused:")

        self.send_response("_You can tell me what to mark as done, wip, cancelled by saying `done 1,3,6` "
                           "for example. To start a new task simply enter a dash and start typing like"
                           " `- new task for today`_")
        self.send_response("_As you do so the message above will update reflecting your standup_")

    def publish(self):
        self.send_response("Publishing to #standup...")
        self.send_response(self.render_task_list(presentation=True), kPublishToChannel, postAsUser=True)
        self.task_list.prune()
        self.main_task_list_ts = None

    def get_task_ids(self, msg):
        if msg.strip():
            split = msg.split(" ")
            if len(split) != 2:
                return None
            else:
                return [int(x) for x in split[1].strip().split(",")]
        else:
            return None


    def mark_status(self, status, task_ids):
        if task_ids:
            for task_id in task_ids:
                if task_id:
                    self.task_list.change_status(task_id, status)

    def add_task(self,msg):
        return self.task_list.add_task(msg)


    def show_task_list(self, update=False):
        return self.send_response(self.render_task_list(), update=update)

    def render_task_list(self, presentation=False):
        past_msg = ""
        new_msg = ""

        for task_id, desc in self.task_list.tasks.items():

            curr_msg = self.render(task_id, desc[1], desc[2], presentation=presentation) + "\n"
            if task_id in self.new_tasks:
                new_msg += curr_msg
            else:
                past_msg += curr_msg

        msg = ""
        if presentation:
            msg = "*Previously* (status changes in _italics_)\n"
            msg += past_msg

            if new_msg:
                msg += "*New Tasks*\n"
                msg += new_msg

        else:
            msg = past_msg + new_msg

        msg += "\n"

        return msg

    def send_response(self, msg, channel=None, update=False, postAsUser=False):
        if not channel:
            channel = self.userid

        action = "chat.update" if update else "chat.postMessage"
        username = self.name + "'s Standup report (via standupbot)" if postAsUser else "Standup report"
        iconurl = self.icon_url if postAsUser else None
        return slack_client.api_call(
            action,
            channel=channel,
            username=username,
            icon_url=iconurl,
            ts=self.main_task_list_ts,
            text=msg
        )

    def get_emoji_for_status(self, status):
        if status == Status.NEW:
            return ":su-todo:"
        elif status == Status.WIP:
            return ":su-wip:"
        elif status == Status.DONE:
            return ":su-done:"
        elif status == Status.CANCELLED:
            return ":su-blocked:"

    def render(self, taskid, desc, status, presentation=False):
        if presentation:
            msg = "{} {}".format(self.get_emoji_for_status(status), desc)
        else:
            msg = "{}:{} {}".format(taskid, self.get_emoji_for_status(status), desc)

        if taskid in self.updated_tasks:
            msg = "_" + msg + "_"
        return msg

if __name__ == "__main__":
    Bot().mainloop()