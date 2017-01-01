import configparser
import censys.export
import censys.query
from base import dict_add_source_prefix
from base import dict_clean_empty
import requests
import json
import re


class CensysObject:

    def __init__(self):
        """Return a CensysObject initialised with API ID and key"""
        config = configparser.ConfigParser()
        config.read("config.ini")
        self.CENSYS_API_ID = (config['SectionOne']['CENSYS_API_ID'])
        self.CENSYS_API_KEY = (config['SectionOne']['CENSYS_API_KEY'])
        self.api = censys.export.CensysExport(api_id=self.CENSYS_API_ID, api_secret=self.CENSYS_API_KEY)

    @staticmethod
    def get_latest_ipv4_tables(self):
        """Returns censys latest ipv4 snapshot string"""
        c = censys.query.CensysQuery(api_id=self.CENSYS_API_ID, api_secret=self.CENSYS_API_KEY)
        numbers = set()
        ipv4_tables = c.get_series_details("ipv4")['tables']
        for string in ipv4_tables:
            splitted_number = string.split('.')[1]
            if splitted_number != 'test':
                numbers.add(splitted_number)
        return max(numbers)

    @staticmethod
    def get_input_choice(self):
        """Returns input_choice represented as integer"""
        items = {'1': 'CIDR', '2': 'ASN', '3': 'CIDR file'}
        input_choice = '0'
        while input_choice not in items:
            input_choice = input("Input: CIDR [1], ASN [2], or CIDR file[3]?")
        return int(input_choice)

    @staticmethod
    def get_user_input_asn(self):
        """Asks user for ASN input and returns valid ASN number"""
        asn = -1
        valid_asn = False

        while not valid_asn:
            asn = input("Enter ASN:")
            if asn.isnumeric():
                asn = int(asn)
                if 0 <= asn <= 4294967295:
                    valid_asn = True
        return asn

    @staticmethod
    def non_sql_get_user_input(self):
        """Returns (non-SQL) Censys query from user input"""
        items = {'2': 'autonomous_system.asn: 1101', '3': 'custom query'}
        choice = '0'
        while choice not in items:
            choice = input("Choose query: (2='autonomous_system.asn: 1101' 3='custom query')")
        chosen_query = items[choice]
        if chosen_query is items['3']:
            chosen_query = input("Enter Query: ")
        return chosen_query

    @staticmethod
    def get_user_input(self):
        """TODO: SQL choice"""

    @staticmethod
    def prepare_ip_or_cidr_query(self, cidr):
        """Return Censys SQL query string for given CIDR"""
        print('Preparing Censys query for ' + str(cidr) + ', total: ' + str(cidr.size))
        latest_table = self.get_latest_ipv4_tables(self)
        # 1 IP query
        if cidr.size is 1:
            return 'select * from ipv4.' + str(latest_table) + ' where ip = "' + str(cidr.network) + '"'
        # CIDR query
        else:
            start = cidr.network
            end = cidr.broadcast
            return 'select * from ipv4.' + str(latest_table) + ' where ipint BETWEEN ' + str(int(start)) + ' AND ' + str(int(end))

    @staticmethod
    def prepare_asn_query(self, asn):
        """Return Censys SQL query string for given CIDR"""
        latest_table = self.get_latest_ipv4_tables(self)
        print('Preparing Censys query for ASN ' + str(asn))
        return 'select * from ipv4.' + str(latest_table) + ' where autonomous_system.asn = ' + str(asn)

    @staticmethod
    def to_file(self, query, str_path_output_file):
        """Makes Censys Export request with given query, converts results and writes to output file"""
        print("Executing query: " + query)

        # Start new Job
        res = self.api.new_job(query)
        job_id = res["job_id"]
        result = self.api.check_job_loop(job_id)

        if result['status'] == 'success':
            print(result)
            for path in result['download_paths']:
                response = requests.get(path)
                data = response.text
                with open(str_path_output_file, 'a') as output_file:
                    # TODO: FIX JSON READ BUG
                    banner = dict_clean_empty(json.loads(data))
                    banner = self.to_es_convert(self, banner)
                    output_file.write(json.dumps(banner) + '\n')
                    print("Appended query results to", str_path_output_file)
        else:
            print('Censys job failed.' + '\n' + str(result))

    @staticmethod
    def to_es_convert(self, input_dict):
        """Return dict ready to be sent to Logstash."""
        # convert ip_int to ipint
        input_dict['ip_int'] = input_dict['ipint']
        del input_dict['ipint']
        # convert autonomous_system.asn to asn
        input_dict['asn'] = input_dict['autonomous_system']['asn']
        del input_dict['autonomous_system']['asn']

        # rename latitude and longitude for geoip
        input_dict['location']['geo'] = {}
        input_dict['location']['geo']['lat'] = input_dict['location']['latitude']
        input_dict['location']['geo']['lon'] = input_dict['location']['longitude']
        del input_dict['location']['latitude']
        del input_dict['location']['longitude']

        #  Remove 'p' from every protocol key
        pattern = re.compile("^p[0-9]{1,6}$")
        for key in input_dict:
            if pattern.match(key):
                input_dict[key[1:]] = input_dict[key]
                del input_dict[key]

        # prefix non-nested fields with 'censys'
        input_dict = dict_add_source_prefix(input_dict, 'censys')
        return input_dict
