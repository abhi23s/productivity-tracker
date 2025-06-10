import json
import os
from datetime import date
from tabulate import tabulate
import math
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']

class Player:
    def __init__(self, username):
        self.username = username
        self.filepath = f"{username}_data.json"
        self.load()

    def get_google_creds(self):
        """Handles Google authentication and returns credentials"""
        creds = None
        if self.data["google_token"]:
            creds = Credentials.from_authorized_user_info(self.data["google_token"])

        # If credentials are expired or invalid, refresh them
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the new credentials
            self.data["google_token"] = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes,
                "expiry": creds.expiry.isoformat() if creds.expiry else None
            }
            self.save()

        return creds

    def load(self):
        try:
            with open(self.filepath, 'r') as f:
                self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {
                "player_name": self.username,
                "level": 0,
                "last_login": None,
                "streak": 0,
                "total_exp": 0,
                "completed_tasks": {},
                "google_token": {}
            }
            self.save()

    def save(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f, indent=4)

    def login(self):
        self.check_due_tasks()
        current_date = date.today()
        last_login = self.data["last_login"]

        if last_login is None:
            self.data["streak"] = 1
        else:
            last_date = date.fromisoformat(last_login)
            delta = (current_date - last_date).days

            if delta == 1:
                self.data["streak"] += 1
            elif delta > 1:
                self.data["streak"] = 1  # reset streak

        self.data["last_login"] = current_date.isoformat()
        self.save()
        print_with_pause("Login Successfull")

    def add_task(self, difficulty, task_name, time_spent):
        tasks = self.data['completed_tasks'].setdefault(difficulty, {})
        task_name = task_name.strip().title()
        today = date.today().isoformat()

        if task_name in tasks:
            tasks[task_name]['count'] += 1
            tasks[task_name]['total_time'] += time_spent
            tasks[task_name]['last_completed'] = today
        else:
            tasks[task_name] = {
            'count': 1,
            'total_time': time_spent,
            'last_completed': today
            }
        streak = self.data["streak"]
        exp_gained = calculate_exp(difficulty, time_spent, streak)
        self.data["total_exp"] = self.data.get("total_exp", 0) + exp_gained
        self.save()
        print_with_pause(f"Task '{task_name}' added under {difficulty} difficulty! Logged {tasks[task_name]} time(s).")

        # calculate Level
        player_xp = self.data["total_exp"]
        player_level = self.data["level"]
        new_level = math.floor(math.log(player_xp / 100 + 1, 2))

        if new_level > player_level:
            print(f"YOU LEVELED UP! Level {new_level}!!GREAT WORK!!!")
            self.data["level"] = new_level
        else:
            self.data["level"] = player_level
        self.save()

    def view_tasks(self):
        print("\n=== Task Log ===")
        for difficulty, tasks in self.data['completed_tasks'].items():
            print(f"\n{difficulty} Tasks:")
            if not tasks:
                print("  No tasks logged.")
            else:
                table_data = []
                headers = ["Task Name", "Count", "Total Time (min)", "Last Completed"]
                
                for task, details in tasks.items():
                    table_data.append([
                        task,
                        details['count'],
                        details['total_time'],
                        details['last_completed']
                    ])
                
                print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def display_stats(self):
        stats_to_show = [
            ("player_name", "Player Name"),
            ("level", "Level"),
            ("last_login", "Last Login"),
            ("streak", "Streak"),
            ("total_exp", "Total XP")
            ]

        table = []
        for key, header in stats_to_show:
            value = self.data.get(key, "")
            if value is None:  # Handle empty last_login
                value = ""
            table.append((header, value))

        print_with_pause(tabulate(table, headers=["Stat",""], tablefmt="grid"), 5)

    def log_task(self):
        task = input("Enter the task: ").strip().title()

        while True:
            difficulty = input("Enter the difficulty (Easy/Medium/Hard/Legendary): ").strip().capitalize()
            if validate_difficulty(difficulty):
                break
            print("Please enter a valid difficulty!")
        while True:
            try:
                time_spent = int(input("Time spent (minutes): "))
                break
            except ValueError:
                print("Please enter a valid number!")

        self.add_task(difficulty, task, time_spent)

    def add_future_task(self):
        if not os.path.exists('credentials.json'):
            print("Google Calendar integration not configured")
            print("Please add credentials.json to enable this feature")
            return
        task = input("Enter future task name: ").strip().title()

        while True:
            due_date = input("Enter due date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(due_date, "%Y-%m-%d")  # Validate date format
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        # Create calendar event
        try:
            creds = self.get_google_creds()
            service = build('calendar', 'v3', credentials=creds)

            event = {
                'summary': f"⏳ TASK DUE: {task}",
                'description': f"Task scheduled via Productivity Tracker",
                'start': {'date': due_date},
                'end': {'date': due_date},
                'reminders': {'useDefault': True},
                }

            event = service.events().insert(calendarId='primary',body=event).execute()

            print(f"\n✅ Task '{task}' added to Google Calendar for {due_date}!")
            print(f"Event ID: {event.get('id')}")

            # Add to future tasks in JSON
            if "future_tasks" not in self.data:
                self.data["future_tasks"] = {}
            self.data["future_tasks"][task] = due_date
            self.save()

        except Exception as e:
            print(f"\n Error adding to Google Calendar: {e}")

    def check_due_tasks(self):
        today = date.today().isoformat()

        if "future_tasks" not in self.data:
            return

        for task, due_date in list(self.data["future_tasks"].items()):
            if due_date <= today:
                print(f"\n Task due: {task} (Due: {due_date})")
                completed = input("Did you complete this task? (y/n): ").lower()

                if completed == 'y':
                    # Log as completed task
                    print("\nLogging completed task:")
                    while True:
                        difficulty = input("Enter the difficulty (Easy/Medium/Hard/Legendary): ").strip().capitalize()
                        if validate_difficulty(difficulty):
                            break
                        print("Please enter a valid difficulty!")

                    time_spent = int(input("Time spent (minutes): "))
                    self.add_task(difficulty, task, time_spent)
                else:
                    # Move to incomplete tasks
                    if "incomplete_tasks" not in self.data:
                        self.data["incomplete_tasks"] = {}
                    self.data["incomplete_tasks"][task] = due_date

                # Remove from future tasks
                del self.data["future_tasks"][task]
                self.save()




def main():
    username = input("Enter your username: ").strip().upper()
    clear_screen()
    player = Player(username)  # Creates/loads user-specific data
    print_with_pause(f"Welcome back {username}!")
    player.display_stats()

    while True:
        print("What would you like to do?")
        print("\n1. Login\n2. Log Task\n3. View Tasks\n4. Stats\n5. Add Future Tasks\n6. Exit")
        choice = input("Choose an option: ").strip()

        if choice == '1':
            player.login()
            clear_screen()
        elif choice == '2':
            player.log_task()
            clear_screen()
        elif choice == '3':
            player.view_tasks()
        elif choice == '4':
            player.display_stats()
        elif choice == '5':
            player.add_future_task()
            clear_screen()
        elif choice == '6':
            print("Goodbye!")
            break
        else:
            print("Invalid choice!")

def calculate_exp(difficulty, time_spent, streak):
    if difficulty == "Easy":
        diff = 1
    elif difficulty == "Medium":
        diff = 2
    elif difficulty == "Hard":
        diff = 3
    elif difficulty == "Legendary":
        diff = 5

    return diff * time_spent + streak


def validate_difficulty(difficulty):
    diff = difficulty.strip().capitalize()
    if diff in ('Easy', 'Medium', 'Hard', 'Legendary'):
        return True
    else:
        return False

def print_with_pause(text, pause_seconds=2):
    print(text)
    time.sleep(pause_seconds)

def clear_screen():
    os.system('cls')



if __name__ == "__main__":
    main()
