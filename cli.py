"""
Copyright (c) 2021 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

import csv
import logging
import math
import os
import secrets
import string
from time import sleep
from typing import final

from meraki.exceptions import APIError
from rich import box, print
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import track, Progress
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.tree import Tree

from meraki_client_vpn_provisioning import MerakiVPN

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "WARN"))

MERAKI_GREEN = "#67b346"
console = Console()

##########
# If this setting is True, this script will only display active Meraki
# networks that contain an MX appliance. If set to False, script will
# return ALL networks that the user has access to, regardless of what
# devices exist in that network.
FILTER_ONLY_MX_NETWORKS = True
##########


def main():
    """
    This is the primary function of this utility.

    This function manages the flow of the utility & handing off most
    processing to sub-functions below for collecting or displaying information.
    """
    # Script start - Print title
    title = Markdown("# **Meraki Client VPN Provisioning Utility**")
    console.print(title)
    console.print("\n")
    console.print("Welcome!", style="bold")

    # Create instance of Meraki VPN utility
    mvpn = MerakiVPN()

    # Begin loop to get API key for Meraki dashboard
    authenticated = False
    while authenticated == False:
        # Retrieve user API key & pass to Meraki utility
        api_key = promptMerakiAPIKey()
        # Store the API key we received
        mvpn.setMerakiAPIKey(api_key)

        # First thing we need to collect is list of Organization IDs.
        # We'll also use this as a test to see if API key is valid.
        try:
            # Try to collect Meraki Orgs
            with console.status(
                f"Connecting to [green]Meraki Dashboard[/green]..."
            ) as status:
                orgs = mvpn.getOrganizations()
            authenticated = True
            console.print(
                "\n[bold green]Successfully authenticated to Meraki Dashboard!"
            )
        except APIError as e:
            # If we couldn't collect Org list, assume API key is bad & restart loop
            console.print("\n[bold red]Error trying to retrieve organizations:")
            console.print(f"[red]{e.message['errors'][0]}")
            console.print("\nLet's try that again....")

    # Ask user what organization to use, then store that org id
    working_org = promptSelectOrg(orgs)
    mvpn.setWorkingOrgID(working_org)

    # Pull list of networks in the working organization
    with console.status("Retrieving list of Meraki networks...") as status:
        networks = mvpn.getNetworks()

    # Prompt user to select which networks to add users
    target_networks = promptSelectNetworks(mvpn, networks)

    # Prompt for operation (add/remove) & method of information entry
    # If manual input is desired, we'll collect that via input prompts
    # If CSV is desired, we'll ask the user to provide the file name
    choice = promptUserInputMethod()
    if choice == "ADD-MANUAL":
        operation = "ADD"
        userList = promptManualUserInput(operation)
    elif choice == "ADD-CSV":
        operation = "ADD"
        userList = promptUploadCSV(operation)
    elif choice == "DEACTIVATE-MANUAL":
        operation = "DEACTIVATE"
        userList = promptManualUserInput(operation)
    elif choice == "DEACTIVATE-CSV":
        operation = "DEACTIVATE"
        userList = promptUploadCSV(operation)

    if operation == "DEACTIVATE":
        # Use list of VPN user email addresses to locate user ID
        # Then use that ID to deactivate each user.
        finalStatus = deactivateUsers(mvpn, userList, target_networks)
    elif operation == "ADD":
        # Use the list of VPN user info to create new Meraki Auth users
        # with authorization for Client VPN
        finalStatus = createUsers(mvpn, userList, target_networks)

    # Check results & print out brief summary of how many success/failures
    successful = 0
    failed = 0
    for task in finalStatus:
        successful += sum(value == True for value in task.values())
        failed += sum(value == False for value in task.values())
    console.print(f"\n\n[bold underline]Final Status:")
    console.print(f"[green]Successfully created: {successful}")
    console.print(f"[red]Failed to create: {failed}")
    console.print(f"Total: {successful + failed}")

    # Confirm if user wants to see detailed status log
    if Confirm.ask(
        "\nShow detailed log? (Includes errors and auto-generated passwords)",
        default=False,
    ):
        printFinalStatus(finalStatus)


def promptMerakiAPIKey():
    """
    Prompt user to enter a Meraki API key

    Parameters:
    None

    Returns:
    key - String containing API key value
    """
    # Begin loop until we receive a valid API key
    while True:
        console.print(
            "In order to get started, please enter your "
            + f"[{MERAKI_GREEN}]Cisco Meraki[/{MERAKI_GREEN}] API key below:"
        )
        key = Prompt.ask("\n[bold]API Key").strip()
        # Check to make sure key is not empty
        if len(key) == 0:
            console.print(
                "[red]Sorry, API key was blank. Please enter a valid API key\n"
            )
            continue

        return key


def promptSelectOrg(orgs):
    """
    Process list of organization IDs. If multiple IDs were returned,
    display them & prompt user to select which one to work with.
    If only one Org ID is found, then just return that Org ID.

    Parameters:
    orgs - List of Meraki organization IDs that API key has access to

    Returns:
    org_id - Single Organization ID that user chose to work with
    """
    org_id = None
    # If user only has access to one org, no reason to ask which one to use.
    if len(orgs) == 1:
        org_id = orgs[0]["id"]
        console.print(f"\nWorking with organization: [blue]{orgs[0]['name']}[/blue]")
        return org_id
    # Otherwise, we'll print out a list of orgs by name & ask which one to use
    console.print("\n")
    org_tree = Tree(f"[green]Meraki Dashboard[/green]")
    counter = 1
    # Build tree of organization names
    for org in orgs:
        org_name = org["name"]
        org_tree.add(f"{counter} - {org_name}")
        counter += 1
    console.print(org_tree)

    # Until user enters valid selection, keep looping & asking for an answer
    while org_id == None:
        console.print("\nPlease select one of the organizations above:")
        selection = Prompt.ask("[bold]Select One")
        try:
            # Check if user input is within range of avaialable options
            if int(selection) in range(1, (len(orgs) + 1)):
                org_num = int(selection) - 1
                org_id = orgs[org_num]["id"]
                console.print(
                    f"\nGot it. We'll work with organization: {orgs[org_num]['name']}"
                )
                return org_id
            else:
                raise (ValueError)
        except ValueError:
            console.print(
                "[bold red]Sorry, that isn't a valid option. Please try again"
            )


def promptSelectNetworks(mvpn, networkList):
    """
    Process Meraki Networks that we have access to & determine which are viable
    candidates to add Client VPN users to. Then prompt user for which networks
    to add users to.

    Parameters:
    mvpn - Instance of Meraki helper class, required to pull device list
    networkList - List of all Meraki networks

    returns:
    target_networks - Dictionary of desired networks in format {"network name": "network id"}
    """
    # In order to display any number of Meraki networks in a readable format,
    # we will build a 4-column grid
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column()
    grid.add_column()
    grid.add_column()

    if FILTER_ONLY_MX_NETWORKS == True:
        # Retrieve Organization-wide device list
        # Note: Pulling Org-wide device list is much more efficient than querying
        #       each network for a list of devices
        deviceList = mvpn.getOrgDevices()

        # Check each device in the list. If device is an MX, store the network ID
        mxList = [
            device["networkId"] for device in deviceList if "MX" in device["model"]
        ]

        # Match network IDs of known MXs to full list of all networks. Only keep
        # networks that contain an MX
        networks = [network for network in networkList if network["id"] in mxList]
    else:
        # Return ALL networks, regardless of if MX is attached
        networks = networkList

    # Grid will have 4 columns. Calculate number of items to figure out how many rows we need
    total = len(networks)
    rows = math.ceil(total / 4)
    console.print(f"\nFound {total} networks!\n")
    counter = 0

    # Sort list of networks by network name
    networks.sort(key=lambda x: x["name"])

    # In order to display networks in each column by descending order,
    # we'll need to build each column here & fill depending on how many
    # total rows we expect.
    # Example: Column 1 = networks 1-20, Column 2 = networks 21-40, etc
    column1 = []
    for each in range(0, rows):
        column1.append(f"{counter + 1} - {networks[counter]['name']}")
        counter += 1
    column2 = []
    for each in range(counter, counter + rows):
        if total == counter:
            break
        column2.append(f"{counter + 1} - {networks[counter]['name']}")
        counter += 1
    column3 = []
    for each in range(counter, counter + rows):
        if total == counter:
            break
        column3.append(f"{counter + 1} - {networks[counter]['name']}")
        counter += 1
    column4 = []
    for each in range(counter, counter + rows):
        if total == counter:
            break
        column4.append(f"{counter + 1} - {networks[counter]['name']}")
        counter += 1

    # Grids are assembled per row, so we'll grab the next value from each
    # column - then create a row.
    for each in track(
        range(0, rows), transient=True, description="Processing networks..."
    ):
        try:
            cell1 = column1[each]
        except:
            cell1 = ""
        counter += 1
        try:
            cell2 = column2[each]
        except:
            cell2 = ""
        counter += 1
        try:
            cell3 = column3[each]
        except:
            cell3 = ""
        counter += 1
        try:
            cell4 = column4[each]
        except:
            cell4 = ""
        counter += 1
        # Inject next row into grid
        grid.add_row(cell1, cell2, cell3, cell4)

    # Display final grid, which will show all networks available to choose from
    console.print(grid)

    # Begin loop to ask user for which networks to focus on.
    # Selection may be a comma-delimited list of networks, a single network,
    # or the 'ALL' keyword for targeting every network
    target_networks = None
    while target_networks == None:
        console.print(
            "\nPlease select one or more networks from above, separated by comma."
        )
        console.print("You may select all networks by using the keyword: ALL")
        input = Prompt.ask("\n[bold]Enter Selection")
        # If ALL: return entire list of all networks in format {"Network Name": "Network ID"}
        if input.lower() == "all":
            target_networks = {network["name"]: network["id"] for network in networks}
            return target_networks
        else:
            # Strip & Parse list of entered numbers
            input_list = [each.strip() for each in input.split(",")]
            try:
                # Build list of network names/IDs based on user input
                # If for some reason user entered number 0, skip it.
                target_networks = {
                    networks[int(num) - 1]["name"]: networks[int(num) - 1]["id"]
                    for num in input_list
                    if num != "0"
                }
                # Grab quick list of the network names (not IDs) to print to user for confirmation
                network_names = [k for k, v in target_networks.items()]
                console.print(f"\nSelected the following networks: {network_names}")
                # Prompt user to confirm networks they have selected
                if not Confirm.ask("Confirm", default=True):
                    target_networks = None
                    continue
                # If input was confirmed, return networks
                return target_networks
            except (ValueError, IndexError):
                # If something isn't recognized, print error & restart loop
                console.print(
                    "[yellow]Sorry, one or more of those entries didn't make sense. Please try again."
                )
                target_networks = None


def promptUserInputMethod():
    """
    Prompt to ask whether user info will be submitted manually or via CSV upload

    Parameters:
    None

    Returns:
    String "MANUAL" or "CSV" - depending on which method user selects
    """
    # Begin loop until we get a valid selection
    while True:
        # Print options
        console.print("\nHow would you like to input user info?")
        console.print("\n1. [white]Add User(s) - Input manually via CLI")
        console.print("2. [white]Add User(s) - Upload local CSV file")
        console.print("3. [white]Deactivate User(s) - Input manually via CLI")
        console.print("4. [white]Deactivate User(s) - Upload local CSV file")
        input = IntPrompt.ask("\n[bold]Enter Selection")
        # Process selection
        if input == 1:
            return "ADD-MANUAL"
        if input == 2:
            return "ADD-CSV"
        if input == 3:
            return "DEACTIVATE-MANUAL"
        if input == 4:
            return "DEACTIVATE-CSV"
        else:
            console.print("\n[yellow]Sorry, that wasn't an option. Please try again.")


def promptManualUserInput(operation):
    """
    If user selected to input VPN user information manually,
    then we'll prompt to input name, email address, and password.
    Can be used to enter one or more sets of user info

    Parameters:
    None

    Returns:
    userList - List containing nested dicts of user information
    """
    userList = []
    # Begin loop to enter user info - continue looping until
    # done entering user info
    while True:
        # Prompt for name, email address, and password
        # Note: Password can be left blank & we'll just auto-generate one
        console.print("\nPlease provide the following details:\n")
        if operation == "DEACTIVATE":
            email = Prompt.ask("[bold]Email")
            username = None
            password = None
        else:
            username = Prompt.ask("[bold]Name")
            email = Prompt.ask("[bold]Email")
            password = Prompt.ask(
                "[bold]Password (leave blank for auto-generate)",
                password=True,
                default=None,
            )
        # Prompt to confirm that informtion is correct.
        # If correct, add user to userList. Otherwise drop the info & restart the prompts
        if not Confirm.ask("\nIs the information correct?", default=True):
            continue
        # If no password provided, go generate one
        if password == None:
            password = generatePassword()
        # Assemble dict of user info, add to the list of all users to create
        user_info = {
            "username": username,
            "email": email,
            "password": password,
        }
        userList.append(user_info)

        # Prompt to ask if more users are needed
        if not Confirm.ask("\nAdd another user?", default=False):
            return userList


def promptUploadCSV(operation):
    """
    If user selected to input VPN user via CSV upload,
    then we'll provide the CSV format & ask for a file name.

    Parameters:
    None

    Returns:
    userList - List containing nested dicts of user information
    """
    userList = []
    # Begin loop to ask for CSV file - continue looping until we have
    # processed a file succesfully
    while True:
        # Print instructions & format of CSV file
        # CSV file format must be:  user name, email address, password
        # Note: Password can be left blank & we'll just auto-generate one
        # Note: CSV file MUST be in same directory as this utility.
        #
        # For deactivating users, format is just: email address
        if operation == "DEACTIVATE":
            console.print(
                "\nExisting VPN users can be bulk deactivated via CSV using the following format:"
            )
            console.print("email address")

            console.print(
                "\nPlease place the CSV in the same directory as this script."
            )
        else:
            console.print(
                "\nNew VPN users can be bulk created via CSV using the following format:"
            )
            console.print("user name, email address, password")
            console.print(
                "Note: Password field may be left blank for an auto-generated password."
            )
            console.print(
                "\nPlease place the CSV in the same directory as this script."
            )

        # Ask for file name
        csv_users = Prompt.ask("[bold]File Name")

        # Load user info from CSV file
        try:
            with open(csv_users, "r") as file:
                csv_reader = csv.reader(file)
                for line in csv_reader:
                    # Only process if line is not emtpy
                    if any(item.strip() for item in line):
                        if operation == "DEACTIVATE":
                            user_info = {
                                "username": None,
                                "email": line[0].strip(),
                            }
                        else:
                            user_info = {
                                "username": line[0].strip(),
                                "email": line[1].strip(),
                            }
                        # Check if CSV row contains a password or not
                        try:
                            user_info["password"] = line[2].strip()
                        except IndexError:
                            # If cell is missing, assume it was left out & generate a random password
                            user_info["password"] = generatePassword()
                        # If blank password field, then go generate a password
                        if user_info["password"] == "":
                            user_info["password"] = generatePassword()
                        # Add dict of user info to list of all users to create
                        userList.append(user_info)
        except FileNotFoundError:
            # If file doens't exist, print error & restart loop to ask again
            console.print(
                "[red]Sorry, we couldn't find that file name. Please try again"
            )
            continue

        # Check count of users to add, confirm before creating
        count = len(userList)
        console.print(f"\nCSV Processed & contains {count} Client VPN users")
        if not Confirm.ask("Proceed?", default=True):
            continue
        return userList


def generatePassword():
    """
    Generate random 24 character password

    Parameters:
    None

    Returns:
    password - randomly-generated 24 character password
    """
    password = "".join(
        (secrets.choice(string.ascii_letters + string.digits) for i in range(24))
    )
    return password


def createUsers(mvpn, userList, target_networks):
    """
    Take in list of users to create & networks to add users to.
    Create job to add each user to the appropriate networks, and
    display progress & errors

    Parameters:
    mvpn - Instance of Meraki helper class, required to execute user creation
    userList - List containing nested dict of user info (name, email, password)
    target_networks - List of network names/IDs where VPN users will be created

    Returns:
    finalStatus - List containing log info for each user, including success/failure & any errors
    """
    finalStatus = []
    with Progress() as progress:
        # Add progress bar for overall job status - which will update every time we complete
        # adding all users to a single network
        console.print("\n[blue]Starting Job...")
        overall_progress = progress.add_task(
            "Overall Progress:", total=len(target_networks), transient=True
        )
        counter = 1
        # Process each network, and add list of users to each network
        for network in target_networks:
            # Print progress display, showing how many tasks remain
            progress.console.print(
                f"[bold reverse]Task {str(counter)} of {str(len(target_networks))}. Network: {network}"
            )
            # Create progress bar for current network, with display name being the network name
            network_progress = progress.add_task(
                f"{network}", total=len(userList), transient=True
            )
            # Iterate through list of users, and add to this network
            for user in userList:
                appliance = f"{network} - appliance"
                net_id = target_networks[network]
                # Send request to create new user, store status/errors
                status = mvpn.createNewVPNUser(
                    net_id, user["username"], user["email"], user["password"], appliance
                )
                # Add other user info to status, so we can pull later to display log
                status["username"] = user["username"]
                status["network"] = network
                status["password"] = user["password"]
                finalStatus.append(status)
                # Update progress display to show status for each user
                if status["success"] == True:
                    progress.console.print(
                        f"{status['username']} - Status: [green]Success!"
                    )
                else:
                    # Pull API error message from APIError object that is returned
                    parsed_error = status["error"].message["errors"][0]
                    # Check if error is just because user already exists... If so, not a true failure
                    if "already exists" in parsed_error:
                        progress.console.print(
                            f"{status['username']} - Status: [yellow] Already active for this network"
                        )
                    else:
                        # If any other error, print failed & we'll display the error in the final status log
                        progress.console.print(
                            f"{status['username']} - Status: [red]Failed (See final status for error)"
                        )
                # Update network progress bar
                progress.update(network_progress, advance=1)
            # Update progress display when single network is done processing
            progress.console.print(f"[cyan]Finished {network}!")
            counter += 1
            # Update overall progress bar
            progress.update(overall_progress, advance=1)
        # Update progress display to notify that ALL processing has been completed
        progress.console.print(f"[green]All tasks completed!")
    # Return list of ALL users and their status
    return finalStatus


def deactivateUsers(mvpn, userList, target_networks):
    """
    Take in list of user email addresses that need to be deactivated
    Create job to locate each user ID & removal process, and
    display progress & errors

    Parameters:
    mvpn - Instance of Meraki helper class, required to execute user creation
    userList - List containing nested dict of user info (name, email, password)
    target_networks - List of network names/IDs where VPN users will be removed

    Returns:
    finalStatus - List containing log info for each user, including success/failure & any errors
    """
    finalStatus = []
    with Progress() as progress:
        # Add progress bar for overall job status - which will update every time we complete
        # removing each user
        console.print("\n[blue]Starting Job...")
        overall_progress = progress.add_task(
            "Overall Progress:", total=len(target_networks), transient=True
        )
        counter = 1
        # Each user ID is unique - but persistent between networks.
        # So we only need to find the user ID from one network
        for user in userList:
            # Print progress display, showing how many tasks remain
            email = user["email"]
            progress.console.print(
                f"[bold reverse]Task {str(counter)} of {str(len(userList))}. User: {email}"
            )
            # Create progress bar for current network, with display name being the network name
            user_progress = progress.add_task(
                f"{email}", total=len(target_networks), transient=True
            )
            # Iterate through list of networks, and query for user ID
            user_id = None
            while user_id == None:
                # Query each network for list of users
                # If we don't find target user, check next network
                # Once we have user ID, continue
                for network in target_networks:
                    net_id = target_networks[network]
                    user_id = mvpn.getMerakiAuthUsers(net_id, email)
                    if user_id == None:
                        continue
                    else:
                        break
                # If User ID is never found:
                if user_id == None:
                    break

            # Skip trying to deactivate if user not found
            if user_id == None:
                progress.console.print(
                        f"{network} - Status: [red]User not found!"
                    )
                status = {"username": email,
                          "network": "ALL",
                          "password": "",
                          "success": False,
                          "error": "User not found"}
                finalStatus.append(status)
                continue
            # Send request to deactivate user
            for network in target_networks:
                net_id = target_networks[network]
                status = mvpn.deactivateUser(net_id, user_id)
                status["username"] = email
                status["password"] = ""
                status["network"] = network
                finalStatus.append(status)
                # Update progress display to show status for each user
                if status["success"] == True:
                    progress.console.print(
                        f"{status['network']} - Status: [green]Success!"
                    )
                else:
                    # If any error, print failed & we'll display the error in the final status log
                    progress.console.print(
                        f"{status['network']} - Status: [red]Failed (See final status for error)"
                    )
                # Update network progress bar
                progress.update(user_progress, advance=1)
            # Update progress display when single network is done processing
            progress.console.print(f"[cyan]Finished {network}!")
            counter += 1
            # Update overall progress bar
            progress.update(overall_progress, advance=1)
        # Update progress display to notify that ALL processing has been completed
        progress.console.print(f"[green]All tasks completed!")
    # Return list of ALL users and their status
    return finalStatus


def printFinalStatus(finalStatus):
    """
    Optional, detailed log of all operations that were performed using this utility.
    This function will create a table that lists every create operation by network & user,
    and show sucess/failure & any error message. Also will display all user passwords,
    which may be helpful if script auto-generated a password that needs to be provided to
    the user.

    Parameters:
    finalStatus - List containing nested dict of all user creation operations & status/errors

    Returns:
    None
    """
    # Build table title & column headers
    table = Table(title="Detailed Log", show_lines=True, box=box.SQUARE_DOUBLE_HEAD)
    table.add_column("Network")
    table.add_column("User")
    table.add_column("Password", no_wrap=True)
    table.add_column("Status")
    table.add_column("Error")

    # Iterate through each log entry, add row containing log info
    for entry in finalStatus:
        # Check what error, if any, so we can add color to status field
        if not entry["error"] == "":
            try:
                parsed_error = entry["error"].message["errors"][0]
            except AttributeError:
                parsed_error = entry["error"]
        else:
            parsed_error = ""
        if entry["success"] == True:
            status = f"[green]Success"
        elif "already exists" in parsed_error:
            status = f"[yellow]Warning"
        else:
            status = "[red]Failed"
        # Add table row containing network name, user name, password, status, and error messaages
        table.add_row(
            entry["network"], entry["username"], entry["password"], status, parsed_error
        )
    # Display Table
    console.print(table)
    console.print("\n\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOkay, See you next time!\n\n")
