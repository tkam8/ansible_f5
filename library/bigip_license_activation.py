#!/usr/bin/python

from ansible.module_utils.basic import *
import json
import time
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)



def get_bigiq_token(data):

	bigiq_username = data['bigiq_username']
	bigiq_password = data['bigiq_password']
	bigiq_server = data['bigiq_server']

	url = "https://{}/mgmt/shared/authn/login" . format(bigiq_server)
	headers = {
		"Content-Type": "application/json"
	}
	body = {
		"username": bigiq_username,
		"password": bigiq_password,
	}

	result = requests.post(url, json.dumps(body), headers=headers, verify=False)
	result_json = result.json()

	return result_json["token"]["token"]



def is_empty_bigiq_regkey(data, bigiq_token, regkey):

	bigiq_server = data['bigiq_server']
	regkey_pool_id = data['regkey_pool_id']

	url = "https://{}/mgmt/cm/device/licensing/pool/regkey/licenses/{}/offerings/{}/members" . format(bigiq_server, regkey_pool_id, regkey)
	headers = {
		"X-F5-Auth-Token": bigiq_token
	}

	result = requests.get(url, headers=headers, verify=False)
	result_json = result.json()

	if len(result_json["items"]) == 0:
		return True
	else:
		return False



def get_bigiq_regkey(data, bigiq_token):

	bigiq_server = data['bigiq_server']
	regkey_pool_id = data['regkey_pool_id']

	url = "https://{}/mgmt/cm/device/licensing/pool/regkey/licenses/{}/offerings" . format(bigiq_server, regkey_pool_id)
	headers = {
		"X-F5-Auth-Token": bigiq_token
	}

	result = requests.get(url, headers=headers, verify=False)
	result_json = result.json()

	for regkey_info in result_json["items"]:
		result = is_empty_bigiq_regkey(data, bigiq_token, regkey_info["regKey"])
		if result:
			return regkey_info["regKey"]

	return ""



def activate_bigip(module, data):

	bigiq_server = data['bigiq_server']
	regkey_pool_id = data['regkey_pool_id']
	bigip_username = data['bigip_username']
	bigip_password = data['bigip_password']
	bigip_server = data['bigip_server']

	# check if already licensed
	while True:
		try:
			url = "https://{}/mgmt/tm/sys/license" . format(bigip_server)
			result = requests.get(url, verify=False, auth=(bigip_username, bigip_password))
			result_json = result.json()
			if "entries" in result_json:
				module.log("(already licensed) ip={}" . format(bigip_server))
				return "done"
			else:
				break
		except:
			module.log("(check license error) ip={}" . format(bigip_server))

		time.sleep(3)


	bigiq_token = get_bigiq_token(data)
	regkey = get_bigiq_regkey(data, bigiq_token)



	module.log("(start) checking management ip")
	url = "https://{}/mgmt/tm/sys/management-ip" . format(bigip_server)
	while True:
		result = requests.get(url, verify=False, auth=(bigip_username, bigip_password))
		result_json = result.json()

		if "items" in result_json:
			break
		else:
			module.log("checking management ip")
			time.sleep(3)

	module.log("(start) checking hostname")
	url = "https://{}/mgmt/tm/sys/global-settings" . format(bigip_server)
	while True:
		result = requests.get(url, verify=False, auth=(bigip_username, bigip_password))
		result_json = result.json()
		hostname = result_json["hostname"]
		if hostname != "bigip1":
			break
		else:
			module.log("hostname is still bigip1")
			time.sleep(3)

	module.log("(start) mgmt ip")
	url = "https://{}/mgmt/tm/sys/global-settings" . format(bigip_server)
	body = {
		"guiSetup": "disabled"
	}
	requests.patch(url, json.dumps(body), verify=False, auth=(bigip_username, bigip_password))

	url = "https://{}/mgmt/tm/sys/config" . format(bigip_server)
	body = {
		"command": "save"
	}
	requests.post(url, json.dumps(body), verify=False, auth=(bigip_username, bigip_password))



	while True:
		url = "https://{}/mgmt/cm/device/licensing/pool/regkey/licenses/{}/offerings/{}/members" . format(bigiq_server, regkey_pool_id, regkey)
		headers = {
			"X-F5-Auth-Token": bigiq_token,
			"Content-Type": "application/json"
		}
		body = {
			"deviceAddress": bigip_server,
			"username": bigip_username,
			"password": bigip_password
		}


		module.log("(start activation) ip={} regkey={}" . format(bigip_server, regkey))

		result = requests.post(url, json.dumps(body), headers=headers, verify=False)
		result_json = result.json()
		if "code" in result_json:
			result_code = result_json["code"]
			module.log("(code) {} (msg) {}" . format(result_code, result_json['message']))
		else:
			break

		time.sleep(3)

	return False, True, "done"



def main():

	fields = {
		"bigiq_server": {"required": True, "type": "str"},
		"regkey_pool_id": {"required": True, "type": "str"},
		"bigiq_username": {"required": True, "type": "str"},
		"bigiq_password": {"required": True, "type": "str"},
		"bigip_username": {"required": True, "type": "str"},
		"bigip_password": {"required": True, "type": "str"},
		"bigip_server": {"required": True, "type": "str"},
	}
	module = AnsibleModule(argument_spec=fields)

	is_error, has_changed, result = activate_bigip(module, module.params)
	if not is_error:
		module.exit_json(changed=has_changed)
	else:
		module.fail_json(msg="Error")



if __name__ == '__main__':
	main()
