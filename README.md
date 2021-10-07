# Meraki Client VPN Provisioning Utiltiy

This project contains a commandline utility for bulk-creation of Meraki Client VPN users, via Meraki Auth. Using this utility, a Meraki admin can add one or more VPN users to one or more networks. The tool supports adding users via manual entry or bulk-upload via CSV file. 

## Contacts
* Matt Schmitz (mattsc@cisco.com)

## Solution Components
* Meraki
* [Rich](https://github.com/willmcgugan/rich)

## Installation/Configuration

*Built & tested with Python 3.8*

**Clone repo:**
```bash
git clone <repo_url>
```

**Install required dependancies:**
```bash
pip install -r requirements.txt
```

## Usage

This tool will prompt for a Meraki API key to use. No other configuration is necessary. 

**Run Utility**
```
python cli.py
```

**Usage Notes:**
- During operation, utility will pull ALL Meraki organizations that the API key has access to & prompt for org selection. If only one org is found, utility will not prompt & instead just assume that is the correct org.
- Utility will only display Meraki networks that contain an active MX appliance. However, utility does *not* check if Client VPN is enabled on each MX, and instead will print an error when attempting to provision users.
- By default, Meraki Dashboard will notify each user by email that they've been added to a new Client VPN network. This utility also asks Dashboard to include the user's password. To not send the password, please change `EMAIL_PASSWORD_TO_USER` to `False` in the `meraki_client_vpn_provisioning.py` file.


# Screenshots

**Example, uploading via CSV file**

![/IMAGES/cli.png](/IMAGES/cli.png)

### LICENSE

Provided under Cisco Sample Code License, for details see [LICENSE](LICENSE.md)

### CODE_OF_CONDUCT

Our code of conduct is available [here](CODE_OF_CONDUCT.md)

### CONTRIBUTING

See our contributing guidelines [here](CONTRIBUTING.md)

#### DISCLAIMER:
<b>Please note:</b> This script is meant for demo purposes only. All tools/ scripts in this repo are released for use "AS IS" without any warranties of any kind, including, but not limited to their installation, use, or performance. Any use of these scripts and tools is at your own risk. There is no guarantee that they have been through thorough testing in a comparable environment and we are not responsible for any damage or data loss incurred with their use.
You are responsible for reviewing and testing any scripts you run thoroughly before use in any non-testing environment.