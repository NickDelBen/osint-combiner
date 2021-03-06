#!/usr/bin/env python3
from timetracker import TimeTracker
from censysfunctions import *
from base import *
import threading
import time
import queue
import argparse
import os
import sys

os.chdir(sys.path[0])

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--convert", help="will also create a converted outputfile", action="store_true")
parser.add_argument("-i", "--institutions", help="will add an institution field to every result based on given csv file "
                                               "in config.ini", action="store_true")
parser.add_argument("-y", "--yes", "--assume-yes", help="Automatic yes to prompts; assume \"yes\" as answer to all "
                                                        "prompts and run non-interactively.", action="store_true")
subparsers = parser.add_subparsers()
query = subparsers.add_parser('queryfile', help='Textfile containing one censys SQL query per line '
                                                '(only the part after WHERE!);')
query.add_argument("inputfile", help="the input file")
query.add_argument('outputfile', help='The file where the results will be stored.')
query.set_defaults(subparser='queryfile')

cidr = subparsers.add_parser('cidrfile', help='Textfile containing CIDRs;')
cidr.add_argument("inputfile", help="the input file")
cidr.add_argument('outputfile', help='The file where the results will be stored.')
cidr.set_defaults(subparser='cidrfile')

csv = subparsers.add_parser('csvfile', help='CSV file containing an organization name and CIDR per row. Multiple rows '
                                            'with the same organization name will be combined. Every organization will '
                                            'have it\'s own output file.')
csv.add_argument("inputfile", help="the input file")
csv.set_defaults(subparser='csvfile')

args = parser.parse_args()
choice = get_input_choice(args)
check_exists_input_file(args.inputfile)
should_convert = args.convert
exit_flag = 0
nr_threads = 4
work_queue = queue.Queue(0)
threads = []
queue_lock = threading.Lock()
t = TimeTracker()


# Threading class for one GET request
class CensysSQLExportThread (threading.Thread):
    def __init__(self, q):
        threading.Thread.__init__(self)
        self.q = q
        self.query = ''
        self.path_output_file = ''
        self.should_convert = False

    def run(self):
        global exit_flag
        while not exit_flag:
            queue_lock.acquire()
            if not work_queue.empty():
                self.query = self.q.get()[0]
                print('Thread got query')
                self.path_output_file = self.q.get()[1]
                print('Thread got path')
                # TODO: find out why it can't get should_convert
                self.should_convert = self.q.get()[2]
                print('Thread got should_convert')
                queue_lock.release()
                print('test2')
                to_file(self.query, self.path_output_file, self.should_convert)
                print('Thread run: ' + self.path_output_file)
                time.sleep(1)
            else:
                queue_lock.release()
            time.sleep(1)


def to_file_organizations():
    global nr_threads
    if len(organizations.items()) < 4:
        nr_threads = len(organizations.items())
    for num in range(1, nr_threads + 1):
        thread = CensysSQLExportThread(work_queue)
        thread.start()
        threads.append(thread)

    # Fill the queue
    with queue_lock:
        latest_table = get_latest_ipv4_tables()
        for name, cidrs in organizations.items():
            organization_query = prepare_cidrs_query(cidrs, latest_table)
            path_output_file = 'outputfiles/censys/censys-' + name
            if should_convert:
                path_output_file += '-converted.json'
            else:
                path_output_file += '.json'
            work_queue.put([organization_query, path_output_file, should_convert])

    # Wait for queue to empty
    while not work_queue.empty():
        pass

    # Notify threads it's time to exit
    global exit_flag
    exit_flag = 1

    # Wait for all GetIpInfoThreads to complete
    for t in threads:
        t.join()

# query file input, single threaded
if choice is 'queryfile':
    check_outputfile(args.outputfile)
    queries = get_queries_per_line_from_file(args.inputfile)
    print('The following Censys queries will be executed:')
    print("\n".join(queries))
    if not args.yes:
        ask_continue()
    for query in queries:
        to_file(prepare_custom_query(query), args.outputfile, should_convert, args.institutions)
# CIDR file input, single threaded
elif choice is 'cidrfile':
    check_outputfile(args.outputfile)
    set_cidrs = parse_all_cidrs_from_file(str(args.inputfile), args.yes)
    query = prepare_cidrs_query(set_cidrs)
    to_file(query, args.outputfile, should_convert, args.institutions)
# CSV file input, multi threaded
elif choice is 'csvfile':
    organizations = get_institutions_from_given_csv(args.inputfile)
    print(organizations.keys())
    print(str(len(organizations)) + ' organizations found.')
    if not args.yes:
        ask_continue()
    to_file_organizations()
t.print_statistics()
