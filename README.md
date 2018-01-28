# A bot focused (only) on the user experience
A standup slack bot which remembers what you did last so it doesn't keep on asking 'what did you do yesterday'. I was trying to bring something simple to Voyage (where I work) but every standup bot out there (I tested about 6) was heavily focused on the task tracking/enterprisy features but not on the actual user experience.

# Features
- Remember and maintain a task list of prior tasks
- be able to quickly mark tasks as done, wip, cancelled
- be able to quickly add new tasks
- generate a report for our slack channel for others to see, marking recent changes.

# Usage
Standuptaskbot is written in python. You need to pip3 install slackclient for it to work.

You need to cp config.py.sample to config.py and add your bot tokens there.

Task status Emojis are currently hardcoded but you can easily edit them in the `get_emoji_for_status` function.

Let me know if you find this useful!

