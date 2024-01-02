import os 
import random
import requests
import time
import datetime 
from dateutil import relativedelta
import threading
import sys
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML

import enquiries
import click
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("CLOCKIFY_API_KEY")

select_workspace = None
select_project = None 
select_workspace_name = None
select_project_name = None
timetrak_tag_id = None

work_note = None
track_start = None
track_end = None

# Change console title 
if sys.platform == "win32":
    os.system("title TimeTrak")
elif sys.platform == "linux":
    sys.stdout.write("\x1b]2;TimeTrak\x07")
elif sys.platform == "darwin":
    sys.stdout.write("\x1b]2;TimeTrak\x07")

def run_enq(prompt_str, choices):
    print(prompt_str, choices)
    completer = WordCompleter(choices)
    choice = prompt(prompt_str, completer=completer)
    return choice

def get_user_info():
    url = "https://api.clockify.me/api/v1/user"
    headers = {
        "X-Api-Key": API_KEY
    }
    response = requests.get(url, headers=headers)
    print(response.json())
    if response.status_code == 200:
        return response.json()["activeWorkspace"]
    else:
        print("Error: " + str(response.status_code))
        return None


def select_workspace():
    global select_workspace, select_workspace_name
    url = "https://api.clockify.me/api/v1/workspaces"
    headers = {
        "X-Api-Key": API_KEY
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        workspaces = response.json()
        workspace_names = [workspace["name"] for workspace in workspaces]
        chosen_workspace = run_enq("Choose a workspace: ", workspace_names)
        for workspace in workspaces:
            if workspace["name"] == chosen_workspace:
                select_workspace = workspace["id"]
                break
        
        select_workspace_name = chosen_workspace
        print("Selected workspace: " + chosen_workspace, select_workspace)
    else:
        print("Error: " + str(response.status_code))
        return

def create_project():
    url = "https://api.clockify.me/api/v1/workspaces/" + select_workspace + "/projects"
    headers = {
        "X-Api-Key": API_KEY
    }
    project_name = click.prompt("Enter project name: ")
    rand_color = "#" + "%06x" % random.randint(0, 0xFFFFFF)
    payload = {
        "name": project_name,
        "note": "TimeTrak created project",
        "clientId": None,
        "isPublic": True,
        "memberships": [],
        "billable": False,
        "color": rand_color,
        "estimate": None,
        "estimateForecast": None,
        "archived": False
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        print("Project created successfully!")
        return project_name, response.json()["id"]
    else:
        print("Error: " + str(response.status_code))
        return None

def select_project():
    global select_project, select_project_name
    url = "https://api.clockify.me/api/v1/workspaces/" + select_workspace + "/projects?archived=false"
    headers = {
        "X-Api-Key": API_KEY
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        projects = response.json()
        project_names = [project["name"] for project in projects]
        project_names.append("Create new project")
        chosen_project = run_enq("Choose a project: ", project_names)
        if chosen_project == "Create new project":
            resp_id, resp_name = create_project()
            if resp_id is not None:
                select_project = resp_id
                chosen_project = resp_name
            else:
                print("Error creating project")
                return
        else: 
            for project in projects:
                if project["name"] == chosen_project:
                    select_project = project["id"]
                    break

        select_project_name = chosen_project
        print("Selected project: " + chosen_project, select_project)
    else:
        print("Error: " + str(response.status_code))
        return

def ensure_tag(): 
    # Check if the tag exists 
    url = "https://api.clockify.me/api/v1/workspaces/" + select_workspace + "/tags"
    headers = {
        "X-Api-Key": API_KEY
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        tags = response.json()
        for tag in tags:
            if tag["name"] == "TimeTrak":
                return tag["id"]
        
        # Tag does not exist, create it 
        url = "https://api.clockify.me/api/v1/workspaces/" + select_workspace + "/tags"
        headers = {
            "X-Api-Key": API_KEY
        }
        payload = {
            "name": "TimeTrak"
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            return response.json()["id"]
        else:
            print("Error: " + str(response.status_code))
            return None

def start_tracking():
    global work_note, track_start

    work_note = click.prompt("Enter work note: ")

    track_start = datetime.datetime.now()

def end_tracking():
    global track_start, track_end, work_note
    click.clear()

    # Print a summary of the time entry 
    print("TimeTrak")
    print("Workspace: " + select_workspace_name)
    print("Project: " + select_project_name)
    print("Work note: " + work_note)
    elapsed_time = relativedelta.relativedelta(track_end, track_start)
    time_difference_str = "Time: {hours}:{minutes}:{seconds}".format(hours=elapsed_time.hours, minutes=elapsed_time.minutes, seconds=elapsed_time.seconds)
    print(time_difference_str)

    options = ["Save", "Discard"]
    choice = enquiries.choose("Save or discard time entry?", options)
    if choice == "Discard":
        print("Discarding time entry")
        return
    
    # Keep or change work note
    options = ["Keep work note", "Change work note"]
    choice = enquiries.choose("Keep or change work note?", options)
    if choice == "Change work note":
        work_note = click.prompt("Enter work note: ")
    
    start_time_str = track_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time_str = track_end.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    url = "https://api.clockify.me/api/v1/workspaces/" + select_workspace + "/time-entries"
    headers = {
        "X-Api-Key": API_KEY
    }
    payload = {
        "start": start_time_str,
        "end": end_time_str,
        "billable": False,
        "description": work_note,
        "projectId": select_project,
        "taskId": None,
        "tagIds": [timetrak_tag_id],
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201 or response.status_code == 200:
        print("Time entry saved successfully!")
        return
    else:
        print("Error: " + str(response.status_code))
        print(response.json())
        return

def bottom_toolbar():
    return HTML('This is a <b><style bg="ansired">Toolbar</style></b>!')

# Will continously display the time elapsed since the start of the current time entry
def display_time():
    global track_start
    try:
        while True:

            # Check if tracking has ended
            if track_end is not None:
                # Kill the thread
                print("Killing thread")
                return

            if track_start:
                elapsed_time = relativedelta.relativedelta(datetime.datetime.now(), track_start)
                # Clear the terminal
                click.clear()
                print("TimeTrak")
                print("Workspace: " + select_workspace)
                print("Project: " + select_project)
                print("Work note: " + work_note)
                time_difference_str = "Timer: {hours}:{minutes}:{seconds}".format(hours=elapsed_time.hours, minutes=elapsed_time.minutes, seconds=elapsed_time.seconds)
                print(time_difference_str)
                print("\r\nPress enter to stop tracking")
            time.sleep(1)
    except KeyboardInterrupt:
        pass

def main():
    global track_end, timetrak_tag_id

    select_workspace()
    select_project()
    timetrak_tag_id = ensure_tag()
    start_tracking()
    timethread = threading.Thread(target=display_time)
    timethread.start()

    # Register Exit handler (enter)
    res = input()
    if res == "":
        track_end = datetime.datetime.now()
        
        while timethread.is_alive():
            time.sleep(1)
        
        end_tracking()

    # buffer1 = Buffer()  # Editable buffer.

    # root_container = VSplit([
    #     # One window that holds the BufferControl with the default buffer on
    #     # the left.
    #     Window(content=BufferControl(buffer=buffer1)),

    #     # A vertical line in the middle. We explicitly specify the width, to
    #     # make sure that the layout engine will not try to divide the whole
    #     # width by three for all these windows. The window will simply fill its
    #     # content by repeating this character.
    #     Window(width=1, char='|'),

    #     # Display the text 'Hello world' on the right.
    #     Window(content=FormattedTextControl(text='Hello world')),
    # ])
    # layout = Layout(root_container)

    # app = application = Application(
    #     full_screen=False,
    #     mouse_support=True,
    #     refresh_interval=1,
    # )
    # app.run()

    # select_workspace()
    # select_project()

    # Start the time display thread
    # time_thread = threading.Thread(target=display_time)
    # time_thread.start()


if __name__ == "__main__":
    main()