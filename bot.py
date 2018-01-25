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

class Bot:
    def __init__(self):
        self.user_list = {}
        self.conversations = {}

    def mainloop(self):
        if slack_client.rtm_connect(with_team_state=False):
            print("Starter Bot connected and running!")
            # Read bot's user ID by calling Web API method `auth.test`
            starterbot_id = slack_client.api_call("auth.test")["user_id"]
            self.user_list = slack_client.api_call("users.list")["members"]
            while True:
                command, channel = self.parse_bot_commands(slack_client.rtm_read())
                if command:
                    self.handle_command(command, channel)
                time.sleep(RTM_READ_DELAY)
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
            self.conversations[from_user] = Conversation(from_user, channel)

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
    WaitingForInit, WaitingForWIP, WaitingForDone, WaitingForCancelled, WaitingForNew, Published = range(6)

    def __init__(self, uid, channel):
        self.current_status = self.WaitingForInit
        self.uid = uid
        self.channel = channel
        self.task_list = taskmanager.get_tasklist(uid)

    def incoming_message(self, message):
        print("Got message: {} for uid {}".format(message, self.uid))

        msg = message.lower()
        if msg.startswith("start"):
            self.current_status = self.WaitingForInit
            if (len(self.task_list.tasks) > 0):
                self.show_task_list()
                self.transition_to_wip()
            else:
                self.transition_to_new()

        elif self.current_status == self.WaitingForWIP:
            self.mark_status(Status.WIP, msg.split(","))
            self.transition_to_done()
        elif self.current_status == self.WaitingForDone:
            self.mark_status(Status.DONE, msg.split(","))
            self.transition_to_cancelled()
        elif self.current_status == self.WaitingForCancelled:
            self.mark_status(Status.CANCELLED, msg.split(","))
            self.transition_to_new()
        elif self.current_status == self.WaitingForNew:
            if msg == 'done':
                self.transition_to_published()
            else:
                self.add_task(msg)

    def mark_status(self, status, task_ids):
        for task_id in task_ids:
            self.task_list.change_status(task_id, status)

    def transition_to_wip(self):
        self.send_response("Which tasks should I mark as :su-wip:? (in csv like 3,5,2)\n")
        self.current_status = self.WaitingForWIP

    def transition_to_done(self):
        self.send_response("And completed tasks :su-done:? (in csv like 3,5,2)\n")
        self.current_status = self.WaitingForDone

    def transition_to_cancelled(self):
        self.send_response("Any tasks blocked :su-blocked:? (in csv like 3,5,2)\n")
        self.current_status = self.WaitingForCancelled

    def transition_to_new(self):
        self.send_response("Tell me what new stuff you are working on one message at a time, say 'done' when done :su-todo:\n")
        self.current_status = self.WaitingForNew

    def transition_to_published(self):
        self.send_response("Thank you, Sharing to #standup\n")
        self.current_status = self.Published
        self.show_task_list()

    def add_task(self,msg):
        self.task_list.add_task(msg)


    def show_task_list(self):
        self.send_response(self.render_task_list())

    def render_task_list(self):
        msg = ""
        for task_id, desc in self.task_list.tasks.items():
            msg += self.render(task_id, desc[0], desc[1]) + "\n"

        msg += "\n"
        return msg

    def send_response(self, msg):
        slack_client.api_call(
            "chat.postMessage",
            channel=self.channel,
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

    def render(self, taskid, desc, status):
        return "{}:{} {}".format(taskid, self.get_emoji_for_status(status), desc)








if __name__ == "__main__":
    Bot().mainloop()