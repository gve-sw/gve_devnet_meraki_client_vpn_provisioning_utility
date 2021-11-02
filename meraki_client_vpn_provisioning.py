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

import logging
import os

import meraki
from meraki.exceptions import APIError


MERAKI_GREEN = "#67b346"
SUPPRESS_MERAKI_LOGGING = True

##########
# By default, ask Meraki Dashboard to email user's password to them.
# Change to False to disable. User will still get notified that
# they've been added to a new Client VPN Network.
EMAIL_PASSWORD_TO_USER = True
##########

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "WARN"))


class MerakiVPN:
    def __init__(self):
        self.MERAKI_API_KEY = None
        self.workingOrgID = None

    def createNewVPNUser(self, network, username, email, password, appliance):
        """
        Send Meraki request to create a new VPN user

        Parameters:
        network - Meraki Network ID where user will be added
        username - Name of user to be added
        email - Email address of user
        password - Client VPN password for this user
        appliance - VPN appliance name, format: "<network name> - appliance"

        Returns dictionary of values indicating success or failure of operation,
        and includes error message if necessary
        """
        # Set required parameters
        account_type = "Client VPN"
        authorizations = [
            {"ssidNumber": 0, "authorizedZone": appliance, "expiresAt": "Never"}
        ]
        logging.info(f"Adding new VPN user ({username}) to network {network}")
        try:
            # Create new user via API
            response = self.dashboard.networks.createNetworkMerakiAuthUser(
                networkId=network,
                accountType=account_type,
                name=username,
                email=email,
                password=password,
                emailPasswordToUser=EMAIL_PASSWORD_TO_USER,
                authorizations=authorizations,
            )
        except Exception as error:
            # Return status as False, provide error info
            logging.info("Error trying to create new user")
            logging.info(error)
            failure = {"success": False, "error": error}
            return failure

        # If no error, then user created successfully
        logging.info("Successfully added new user")
        success = {"success": True, "password": password, "error": ""}
        return success

    def setMerakiAPIKey(self, api_key):
        """
        Update Meraki API key for this instance
        """
        self.MERAKI_API_KEY = api_key
        log.info(f"Set Meraki API key to {api_key}")
        self.dashboard = meraki.DashboardAPI(
            self.MERAKI_API_KEY, suppress_logging=SUPPRESS_MERAKI_LOGGING
        )

    def getOrganizations(self):
        """
        Pull list of Organization IDs from Meraki Dashboard
        """
        orgs = self.dashboard.organizations.getOrganizations()
        count = len(orgs)
        log.info(f"Successfully retrieved {count} organization IDs")
        return orgs

    def setWorkingOrgID(self, org_id):
        """
        Store Org ID that we are working on
        """
        self.workingOrgID = org_id
        log.info(f"Set working organization ID to: {org_id}")

    def getNetworks(self):
        """
        Retrieve list of networks within the organization
        """
        networks = self.dashboard.organizations.getOrganizationNetworks(
            self.workingOrgID
        )
        count = len(networks)
        log.info(f"Successfully retrieved {count} networks")
        return networks

    def getOrgDevices(self):
        """
        Get List of ALL organization devices
        """
        deviceList = self.dashboard.organizations.getOrganizationDevices(
            self.workingOrgID, productTypes=["appliance"]
        )
        return deviceList

    def getMerakiAuthUsers(self, network_id, email_address):
        """
        Query for Meraki Auth user by network & user email address
        Return Meraki user ID
        """
        userList = self.dashboard.networks.getNetworkMerakiAuthUsers(network_id)
        if len(userList) == 0:
            log.info("Found no Meraki Auth users")
            return None
        else:
            for user in userList:
                if user["email"] == email_address:
                    return user["id"]

    def deactivateUser(self, network_id, user_id):
        """
        Deactivate a single Meraki Auth user by user ID
        """
        try:
            self.dashboard.networks.deleteNetworkMerakiAuthUser(network_id, user_id)
            success = {"success": True, "error": ""}
            return success
        except APIError as error:
            failure = {"success": False, "error": error}
            return failure