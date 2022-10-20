# Copyright 2022 Red Hat, Inc.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
Simple module to test vault_load_secrets
"""

import json
import os
import sys
import unittest
from unittest.mock import call, patch

from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes

sys.path.insert(1, "./ansible/plugins/modules")
import vault_load_secrets  # noqa: E402


def set_module_args(args):
    """prepare arguments so that they will be picked up during module creation"""
    args = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(args)


class AnsibleExitJson(Exception):
    """Exception class to be raised by module.exit_json and caught by the test case"""

    pass


class AnsibleFailJson(Exception):
    """Exception class to be raised by module.fail_json and caught by the test case"""

    pass


def exit_json(*args, **kwargs):
    """function to patch over exit_json; package return data into an exception"""
    if "changed" not in kwargs:
        kwargs["changed"] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args, **kwargs):
    """function to patch over fail_json; package return data into an exception"""
    kwargs["failed"] = True
    kwargs["args"] = args
    raise AnsibleFailJson(kwargs)


class TestMyModule(unittest.TestCase):
    def setUp(self):
        self.mock_module_helper = patch.multiple(
            basic.AnsibleModule, exit_json=exit_json, fail_json=fail_json
        )
        self.mock_module_helper.start()
        self.addCleanup(self.mock_module_helper.stop)
        self.testdir = os.path.dirname(os.path.abspath(__file__))

    def test_module_fail_when_required_args_missing(self):
        with self.assertRaises(AnsibleFailJson):
            set_module_args({})
            vault_load_secrets.main()

    def test_module_fail_when_values_secret_not_existing(self):
        with self.assertRaises(AnsibleExitJson) as ansible_err:
            set_module_args(
                {
                    "values_secrets": "/tmp/nonexisting",
                }
            )
            vault_load_secrets.main()

        ret = ansible_err.exception.args[0]
        self.assertEqual(ret["failed"], True)
        self.assertEqual(ret["error"], "Missing values-secrets.yaml file")
        self.assertEqual(
            ret["msg"], "Values secrets file does not exist: /tmp/nonexisting"
        )

    def test_ensure_empty_files_but_not_secrets_is_ok(self):
        set_module_args(
            {
                "values_secrets": os.path.join(
                    self.testdir,
                    "values-secret-empty-files.yaml",
                )
            }
        )

        with patch.object(vault_load_secrets, "run_command") as mock_run_command:
            stdout = "configuration updated"
            stderr = ""
            ret = 0
            mock_run_command.return_value = ret, stdout, stderr  # successful execution

            with self.assertRaises(AnsibleExitJson) as result:
                vault_load_secrets.main()
            self.assertTrue(
                result.exception.args[0]["changed"]
            )  # ensure result is changed
            assert mock_run_command.call_count == 2

        calls = [
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/hub/config-demo' secret='VALUE'\""  # noqa: E501
            ),
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/hub/aws' access_key_id='VALUE' secret_access_key='VALUE'\""  # noqa: E501
            ),
        ]
        mock_run_command.assert_has_calls(calls)

    def test_ensure_broken_files_fail(self):
        for i in (
            "values-secret-broken1.yaml",
            "values-secret-broken2.yaml",
            "values-secret-broken3.yaml",
        ):
            with self.assertRaises(AnsibleFailJson) as ansible_err:
                set_module_args({"values_secrets": os.path.join(self.testdir, i)})
                vault_load_secrets.main()

            ret = ansible_err.exception.args[0]
            self.assertEqual(ret["failed"], True)

    def test_ensure_empty_secrets_but_not_files_is_ok(self):
        set_module_args(
            {
                "values_secrets": os.path.join(
                    self.testdir,
                    "values-secret-empty-secrets.yaml",
                )
            }
        )

        with patch.object(vault_load_secrets, "run_command") as mock_run_command:
            stdout = "configuration updated"
            stderr = ""
            ret = 0
            mock_run_command.return_value = ret, stdout, stderr  # successful execution

            with self.assertRaises(AnsibleExitJson) as result:
                vault_load_secrets.main()
            self.assertTrue(
                result.exception.args[0]["changed"]
            )  # ensure result is changed
            assert mock_run_command.call_count == 1

        calls = [
            call(
                "cat '/home/michele/.ssh/id_rsa.pub' | oc exec -n vault vault-0 -i -- sh -c 'cat - > /tmp/vcontent'; oc exec -n vault vault-0 -i -- sh -c 'base64 --wrap=0 /tmp/vcontent | vault kv put secret/hub/publickey b64content=- content=@/tmp/vcontent; rm /tmp/vcontent'"  # noqa: E501
            ),
        ]
        mock_run_command.assert_has_calls(calls)

    def test_ensure_command_called(self):
        set_module_args(
            {"values_secrets": os.path.join(self.testdir, "values-secret.yaml")}
        )

        with patch.object(vault_load_secrets, "run_command") as mock_run_command:
            stdout = "configuration updated"
            stderr = ""
            ret = 0
            mock_run_command.return_value = ret, stdout, stderr  # successful execution

            with self.assertRaises(AnsibleExitJson) as result:
                vault_load_secrets.main()
            self.assertTrue(
                result.exception.args[0]["changed"]
            )  # ensure result is changed
            assert mock_run_command.call_count == 9

        calls = [
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/hub/config-demo' secret='demo123'\""  # noqa: E501
            ),
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/hub/googleapi' key='lskdjflskjdflsdjflsdkjfldsjkfldsj'\""  # noqa: E501
            ),
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/hub/cluster_alejandro' name='alejandro' bearerToken='sha256~bumxi-012345678901233455675678678098-abcdef'\""  # noqa: E501
            ),
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/hub/test' s3.accessKey='1234' s3.secretKey='4321' s3Secret='czMuYWNjZXNzS2V5OiAxMjM0CnMzLnNlY3JldEtleTogNDMyMQ=='\""  # noqa: E501
            ),
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/hub/test2' s3.accessKey='accessKey' s3.secretKey='secretKey' s3Secret='fooo'\""  # noqa: E501
            ),
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/hub/test3' s3.accessKey='aaaaa' s3.secretKey='bbbbbbbb' s3Secret='czMuYWNjZXNzS2V5OiBhYWFhYQpzMy5zZWNyZXRLZXk6IGJiYmJiYmJi'\""  # noqa: E501
            ),
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/region-one/config-demo' secret='region123'\""  # noqa: E501
            ),
            call(
                "cat '/home/michele/ca.crt' | oc exec -n vault vault-0 -i -- sh -c 'cat - > /tmp/vcontent'; oc exec -n vault vault-0 -i -- sh -c 'base64 --wrap=0 /tmp/vcontent | vault kv put secret/hub/cluster_alejandro_ca b64content=- content=@/tmp/vcontent; rm /tmp/vcontent'"  # noqa: E501
            ),
            call(
                "cat '/home/michele/ca.crt' | oc exec -n vault vault-0 -i -- sh -c 'cat - > /tmp/vcontent'; oc exec -n vault vault-0 -i -- sh -c 'base64 --wrap=0 /tmp/vcontent | vault kv put secret/region-one/ca b64content=- content=@/tmp/vcontent; rm /tmp/vcontent'"  # noqa: E501
            ),
        ]
        mock_run_command.assert_has_calls(calls)

    def test_ensure_good_template_checking(self):
        set_module_args(
            {
                "values_secrets": os.path.join(self.testdir, "mcg-values-secret.yaml"),
                "check_missing_secrets": True,
                "values_secret_template": os.path.join(
                    self.testdir, "template-mcg-working.yaml"
                ),
            }
        )
        with patch.object(vault_load_secrets, "run_command") as mock_run_command:
            stdout = "configuration updated"
            stderr = ""
            ret = 0
            mock_run_command.return_value = ret, stdout, stderr  # successful execution

            with self.assertRaises(AnsibleExitJson) as result:
                vault_load_secrets.main()
            self.assertTrue(
                result.exception.args[0]["changed"]
            )  # ensure result is changed
            assert mock_run_command.call_count == 1

        calls = [
            call(
                "oc exec -n vault vault-0 -i -- sh -c \"vault kv put 'secret/hub/config-demo' secret='VALUE' additionalsecret='test'\""  # noqa: E501
            ),
        ]
        mock_run_command.assert_has_calls(calls)

    def test_ensure_bad_template_checking(self):
        set_module_args(
            {
                "values_secrets": os.path.join(self.testdir, "mcg-values-secret.yaml"),
                "check_missing_secrets": True,
                "values_secret_template": os.path.join(
                    self.testdir, "template-mcg-missing.yaml"
                ),
            }
        )
        with patch.object(vault_load_secrets, "run_command") as mock_run_command:
            stdout = "configuration updated"
            stderr = ""
            ret = 0
            mock_run_command.return_value = ret, stdout, stderr

            with self.assertRaises(AnsibleFailJson) as result:
                vault_load_secrets.main()
            self.assertTrue(result.exception.args[0]["failed"])
            # In case of failure args[1] contains the msg of the failure
            assert (
                result.exception.args[0]["args"][1]
                == "Values secret yaml is missing needed secrets from the templates: {'secrets.config-demo.foo'}"
            )
            assert mock_run_command.call_count == 0


if __name__ == "__main__":
    unittest.main()
