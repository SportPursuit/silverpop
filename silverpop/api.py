import requests
import logging

from xml.etree import ElementTree

from silverpop.xml import ConvertXmlToDict, ConvertDictToXml
from silverpop.exceptions import AuthException, ResponseException

RAW_DATA_EXPORT_DATE_FORMAT = '%m/%d/%Y %H:%M:%S'

logger = logging.getLogger(__name__)

class API(object):

    def __init__(self, url, username=None, password=None, sessionid=None):
        self.url = url
        self.username = username
        self.password = password
        self.sessionid = sessionid if sessionid else self.login()

    def login(self):
        """ Connects to Silverpop and attempts to retrieve a jsessionid for secure request purposes.
        """
        if not (self.username and self.password):
            return
        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {'Login': {'USERNAME': self.username, 'PASSWORD': self.password}}

        response, success = self._submit_request(xml, retry=False, auth=True)
        sessionid = response.get('SESSIONID') if success else None

        if not sessionid:
            raise AuthException()

        logger.info("New Silverpop sessionid acquired: %s", sessionid)

        return sessionid

    def get_user_info(self, list_id, email):
        """ Returns data from the specified list about the specified user.
            The email address must be used as the primary key.
        """
        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'SelectRecipientData': {
                'LIST_ID': list_id,
                'EMAIL': email
            }
        }
        result, success = self._submit_request(xml)

        return result, success

    def add_recipient(self, list_id, email, data=None):
        """ Mask for add_user
        """
        data = data or {}
        return self.add_user(list_id, email, data=data)

    def add_user(self, list_id, email, data=None):
        """ Adds a user to the specified list. Supports adding additional attributes
            via passing a dictionary to the data parameter.
        """
        data = data or {}

        # Build the XML
        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'AddRecipient': {
                'LIST_ID': list_id,
                'CREATED_FROM': 2,
                'COLUMN': [
                    {'NAME': 'EMAIL', 'VALUE': email}
                ],
            }
        }

        xml['Envelope']['Body']['AddRecipient']['COLUMN'].extend(
            self._data_to_columns(data)
        )

        result, success = self._submit_request(xml)

        return result, success

    def add_contact_to_contact_list(self, contact_list_id, contact_id=None, data=None):
        """ Adds a contact by contact_id or by performing a search based on
            the data parameter.
        """
        data = data or {}
        assert contact_list_id or len(data) >= 1, 'Contact_list_id or data parameter must be set'

        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'AddContactToContactList': {
                'CONTACT_LIST_ID': contact_list_id,
            }
        }

        if contact_id:
            xml['Envelope']['Body']['AddContactToContactList'].update({'CONTACT_ID': contact_id})

        elif data:
            xml['Envelope']['Body']['AddContactToContactList'].update({'COLUMN': self._data_to_columns(data)})

        result, success = self._submit_request(xml)
        return result, success

    def remove_recipient(self, list_id, email):
        self.remove_user(list_id, email)

    def remove_user(self, list_id, email):
        """ Removes a user from the specified list.
        """
        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'RemoveRecipient': {
                'LIST_ID': list_id,
                'EMAIL': email,
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def logout(self):
        raw_xml = """<Envelope><Body><Logout/></Body></Envelope>"""
        result, success = self._submit_request(raw_xml, raw_xml=True)

        return result, success

    def update_recipient(self, list_id, email, data):
        self.update_user(list_id, email, data)

    def update_user(self, list_id, email, data):
        """ Updates an existing user in Silverpop based on the email address as
            the primary key. The data parameter is a dictionary that maps column
            names to their new values.
        """

        assert len(data) >= 1, \
            'Data parameter must contain at least one column/value pair'

        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'UpdateRecipient': {
                'LIST_ID': list_id,
                'CREATED_FROM': 2,
                'OLD_EMAIL': email,
                'COLUMN': self._data_to_columns(data),
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def opt_out_user(self, list_id, email):
        """ Opts a user out on the specified list.
        """
        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'OptOutRecipient': {
                'LIST_ID': list_id,
                'EMAIL': email,
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def import_list(self, map_filename, list_filename):
        """ Imports a Relational Table using a CSV and an XML mapping file, previously uploaded.

            <Envelope>
                <Body>
                    <ImportList>
                        <MAP_FILE>list_import_map.xml</MAP_FILE>
                        <SOURCE_FILE>list_create.csv</SOURCE_FILE>
                    </ImportList>
                </Body>
            </Envelope>
        """
        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'ImportList': {
                'MAP_FILE': map_filename,
                'SOURCE_FILE': list_filename,
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def import_table(self, map_filename, table_filename):
        """ Imports a Relational Table using a CSV and an XML mapping file, previously uploaded.

            <Envelope>
                <Body>
                    <ImportTable>
                        <MAP_FILE>table_import_map.xml</MAP_FILE>
                        <SOURCE_FILE>table_create.csv</SOURCE_FILE>
                    </ImportTable>
                </Body>
            </Envelope>
        """
        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'ImportTable': {
                'MAP_FILE': map_filename,
                'SOURCE_FILE': table_filename,
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def set_column_value(self, id, col_name, col_value=None):
        """ Sets the value of a column in the provided Database or Query ID, to the provided value, or resetting it, if
            the value is not provided. Example:

            <Envelope>
                <Body>
                    <SetColumnValue>
                        <LIST_ID>3126420</LIST_ID>
                        <COLUMN_NAME>recency_sport_1</COLUMN_NAME>
                        <COLUMN_VALUE>Hiking</COLUMN_VALUE>
                        <ACTION>1</ACTION>
                    </SetColumnValue>
                </Body>
            </Envelope>
        """

        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'SetColumnValue': {
                'LIST_ID': id,
                'COLUMN_NAME': col_name,
                'ACTION': 0,
            }
        }

        # if provided a col_value, then change the action (0 = Reset, 1 = Update) and add the COLUMN_VALUE field
        if col_value is not None:
            xml['Envelope']['Body']['SetColumnValue']['ACTION'] = 1
            xml['Envelope']['Body']['SetColumnValue']['COLUMN_VALUE'] = col_value

        result, success = self._submit_request(xml)

        return result, success

    def raw_recipient_data_export(self, list_id, columns, start_date, end_date, filename=None):
        """ Requests for a raw recipient data export from Silverpop, given start date, end date and a list of columns:

            <Envelope>
                <Body>
                    <RawRecipientDataExport>
                        <INCLUDE_CHILDREN>1</INCLUDE_CHILDREN>
                        <OPTOUTS>1</OPTOUTS>
                        <MOVE_TO_FTP>1</MOVE_TO_FTP>
                        <EXPORT_FILE_NAME>Export_file_name</EXPORT_FILE_NAME>
                        <OPENS>1</OPENS>
                        <EVENT_DATE_START>01/24/2017 00:00:00</EVENT_DATE_START>
                        <CLICKS>1</CLICKS>
                        <COLUMNS>
                            <COLUMN>
                                <NAME>col1</NAME>
                            </COLUMN>
                            <COLUMN>
                                <NAME>col2</NAME>
                            </COLUMN>
                            <COLUMN>
                                <NAME>col3</NAME>
                            </COLUMN>
                            <COLUMN>
                                <NAME>col4</NAME>
                            </COLUMN>
                        </COLUMNS>
                        <EVENT_DATE_END>01/24/2017 23:59:59</EVENT_DATE_END>
                        <LIST_ID>111111</LIST_ID>
                        <LIST_ID>222222</LIST_ID>
                        <EXCLUDE_DELETED>1</EXCLUDE_DELETED>
                        <EXPORT_FORMAT>0</EXPORT_FORMAT>
                        <SOFT_BOUNCES>1</SOFT_BOUNCES>
                        <SENT>1</SENT>
                    </RawRecipientDataExport>
                </Body>
            </Envelope>

            :returns    ({
                            'MAILING': {
                                'FILE_PATH': 'MerlynRawRecipientDataExport Jan 24 2017 15-53-54 PM 369.zip',
                                'JOB_ID': '97348251'},
                            'SUCCESS': 'TRUE'
                        },
                        True)
        """

        if filename is None:
            filename = 'MerlynRawRecipientDataExport'

        start_date_string = start_date.strftime(RAW_DATA_EXPORT_DATE_FORMAT)
        end_date_string = end_date.strftime(RAW_DATA_EXPORT_DATE_FORMAT)

        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'RawRecipientDataExport': {
                'EVENT_DATE_START': start_date_string,
                'EVENT_DATE_END': end_date_string,
                'EXPORT_FORMAT': 0,
                'LIST_ID': list_id,
                'EXCLUDE_DELETED': 1,
                'INCLUDE_CHILDREN': 1,
                'OPENS': 1,
                'CLICKS': 1,
                'SENT': 1,
                'OPTOUTS': 1,
                'SOFT_BOUNCES': 1,
                'HARD_BOUNCES': 1,
                'EXPORT_FILE_NAME': filename,
                'MOVE_TO_FTP': 1,
                'MAIL_BLOCKS': 1,
                'REPLY_ABUSE': 1,
                'COLUMNS': {'COLUMN': [{'NAME': c} for c in columns]}
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def get_job_status(self, job_id):
        """
        <Envelope>
            <Body>
                <GetJobStatus>
                    <JOB_ID> 97211166 </JOB_ID>
                </GetJobStatus>
            </Body>
        </Envelope>
        :returns    ({
                        'JOB_ID': '97348251',
                        'JOB_STATUS': 'COMPLETE',
                        'JOB_DESCRIPTION': 'Description,
                        'PARAMETERS': [{
                            'PARAMETER': {
                                'NAME': 'name'
                                'VALUE': 'value
                            }
                        }]
                        'SUCCESS': 'TRUE'
                    },
                    True)
        """

        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'GetJobStatus': {
                'JOB_ID': job_id
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def get_sent_mailings_for_org(self, start_date, end_date):
        """
        <Envelope>
            <Body>
                <GetSentMailingsForOrg>
                    <DATE_START>02/06/2017 00:00:00</DATE_START>
                    <DATE_END>02/06/2017 23:59:59</DATE_END>
                    <EXCLUDE_ZERO_SENT/>
                    <EXCLUDE_TEST_MAILINGS/>
                </GetSentMailingsForOrg>
            </Body>
        </Envelope>
        :returns    ({'Mailing': [
                            {'ListId': '8329850',
                            'ListName': 'Undelivered 1st Contact Query to edit',
                            'MailingId': '16498162',
                            'MailingName': 'Undelivered email template - 1st contact (16)',
                            'NumSent': '12',
                            'ParentListId': '1903827',
                            'ParentTemplateId': '14597470',
                            'ReportId': '960471871',
                            'ScheduledTS': '2017-02-06 17:11:07.0',
                            'SentTS': '2017-02-06 17:11:11.0',
                            'Subject': 'Your SportPursuit Order - Product Returned',
                            'UserName': 'Victoria Walton',
                            'Visibility': 'Shared'}, ...
                            ],
                        'SUCCESS': 'TRUE'},
                    True)
        """

        start_date_string = start_date.strftime(RAW_DATA_EXPORT_DATE_FORMAT)
        end_date_string = end_date.strftime(RAW_DATA_EXPORT_DATE_FORMAT)

        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'GetSentMailingsForOrg': {
                'DATE_START': start_date_string,
                'DATE_END': end_date_string,
                'EXCLUDE_ZERO_SENT': 1,
                'EXCLUDE_TEST_MAILINGS': 1,
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def _sanitize_columns_in_api_result(self, data):
        """ Post result parsing, the value of the columns key, if it exists,
            will look something this format:

            COLUMNS:[{'COLUMN':{'NAME':'<name>', 'VALUE':'<value>'}, ...}]. This
            method replaces the value of the columns key with a dictionary that
            looks like this:

            COLUMNS: {'<name>': <value>}
        """
        columns = data.get('COLUMNS', {}).get('COLUMN', [])

        # Don't touch the original data if there aren't any columns.
        if len(columns) < 1:
            return data

        out = {}
        if type(columns) == dict:
            out[columns['NAME']] = columns['VALUE']
        else:
            for column in columns:
                if column['NAME'].lower() != 'url':
                    out[column['NAME']] = column['VALUE']

        data['COLUMNS'] = out

        return data

    def _data_to_columns(self, data):
        """ Iterates through a data dictionary, building a list of the format
            [{'NAME':'<name>', 'VALUE':'<value>'},...]. The result can be set to
            the COLUMN key in a dictionary that will be converted to XML for
            Silverpop consumption.
        """
        assert callable(getattr(data, 'items', None)), 'Data parameter must have a callable called items'

        # Append the data dictionary to the column list
        columns = []
        for column, value in data.items():
            columns.append({'NAME': column, 'VALUE': value, })

        return columns

    def _get_xml_document(self):
        return {'Envelope': {'Body': {}}}

    def _submit_request(self, xml_dict, retry=True, auth=False, raw_xml=False):
        """ Submits an XML payload to Silverpop, parses the result, and returns it.
        """
        if not raw_xml:
            xml = ElementTree.tostring(ConvertDictToXml(xml_dict))
        else:
            xml = xml_dict

        url = '%s;jsessionid=%s' % (self.url, self.sessionid) if not auth else self.url

        logger.debug("Sending request to: %s", url)

        # Connect to silverpop and get our response
        response = requests.post(url, data=xml, headers={"Content-Type": "text/xml;charset=utf-8"})
        response.raise_for_status()

        logger.debug("Recieved response: %s", response.content)

        response = ConvertXmlToDict(response.content, dict)
        response = response.get('Envelope', {}).get('Body')

        # Determine if the request succeeded
        success = response.get('RESULT', {}).get('SUCCESS', 'false').lower() in ('true', 'success')

        # Generate an exception if the API request failed.
        if not success:
            exc = ResponseException(response['Fault'])
            error_id = exc.fault.get('detail', {}).get('error', {}).get('errorid', None)

            # We want to try and resend the request on auth failures if retry
            # is enabled. 140 is the error_id for unauthenticated api attempts
            if error_id == str(140) and retry:
                self.sessionid = self.login()
                return self._submit_request(xml_dict, retry=False)
            elif auth:
                pass
            else:
                raise exc

        return self._sanitize_columns_in_api_result(response['RESULT']), success

    def get_scheduled_mailings_for_org(self):

        """
        <Envelope>
		  <Body>
			<GetSentMailingsForOrg>
			  <SCHEDULED/>
			  <EXCLUDE_TEST_MAILINGS/>
			</GetSentMailingsForOrg>
		  </Body>
		</Envelope>
        :returns    ({'Mailing': [
                            {'ListId': '8329850',
                            'ListName': 'Undelivered 1st Contact Query to edit',
                            'MailingId': '16498162',
                            'MailingName': 'Undelivered email template - 1st contact (16)',
                            'NumSent': '12',
                            'ParentListId': '1903827',
                            'ParentTemplateId': '14597470',
                            'ReportId': '960471871',
                            'ScheduledTS': '2017-02-06 17:11:07.0',
                            'SentTS': '2017-02-06 17:11:11.0',
                            'Subject': 'Your SportPursuit Order - Product Returned',
                            'UserName': 'Victoria Walton',
                            'Visibility': 'Shared'}, ...
                            ],
                        'SUCCESS': 'TRUE'},
                    True)
        """

        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'GetSentMailingsForOrg': {
                'SCHEDULED': 1,
                'EXCLUDE_TEST_MAILINGS': 1,
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def purge_data(self, target_id, source_id):

        """
        <Envelope>
		  <Body>
			<PurgeData>
			  <TARGET_ID>7416984</TARGET_ID>
			  <SOURCE_ID>11894739</SOURCE_ID>
			</PurgeData>
		  </Body>
		</Envelope>
        :returns    ({'SUCCESS': 'TRUE', 'JOB_ID': '204693296'}, True)
        """

        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'PurgeData': {
                'TARGET_ID': target_id,
                'SOURCE_ID': source_id,
            }
        }

        result, success = self._submit_request(xml)

        return result, success

    def calculate_query(self, query_id):

        """
		<Envelope>
			<Body>
				<CalculateQuery>
					<QUERY_ID>12503807</QUERY_ID>
				</CalculateQuery>
			</Body>
		</Envelope>
        :returns    ({'SUCCESS': 'TRUE', 'JOB_ID': '204757320'}, True)
        """

        xml = self._get_xml_document()
        xml['Envelope']['Body'] = {
            'CalculateQuery': {
                'QUERY_ID': query_id,
            }
        }

        result, success = self._submit_request(xml)

        return result, success
