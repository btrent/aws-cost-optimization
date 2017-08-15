#!/usr/bin/python

import boto3
from datetime import date, datetime, timedelta
import json
import sys

creds_file = '/home/ec2-user/.aws/credentials'
print_all = False
show_unused_reserved = True
suggest_reserved = True
suggest_resize = False
large_sizes = ['2xlarge', '4xlarge', '8xlarge', '16xlarge', '32xlarge']
resize_cpu_utilization_threshold = 1 #percent average CPU utilization
suggest_reserved_threshold = 120 #days unreserved instance has been running

#print json.dumps(instances, indent=4, sort_keys=True, default=json_serial)
def main():
    global print_all, show_unused_reserved, suggest_reserved, suggest_resize

    creds = load_creds()
    reserved = []

    for cred in creds:
        ec2 = boto3.client('ec2', aws_access_key_id=cred[1], aws_secret_access_key=cred[2])
        cw = boto3.client('cloudwatch', aws_access_key_id=cred[1], aws_secret_access_key=cred[2])
        instances = get_running_instances(ec2, cw)
    
        process_reserved_instances(ec2, instances, reserved, cred[0])

        for i in instances:
            if print_all is True:
                print_instance(i)
            if suggest_reserved is True:
                check_reservable(i)
            if suggest_resize is True:
                check_resizable(i)

    # After processing all accounts, see if we have any reserved instances unaccounted for
    if show_unused_reserved is True:
        for r in reserved:
            if (r is not None):
                print '\nUnused reserved instance:'
                print "\tInstance Type: " + r['InstanceType']
                print "\tAvailability Zone: " + r['AvailabilityZone']
                print "\tAccount: " + r['AccountName']

def process_reserved_instances(ec2, instances, reserved, account_name):
    for x in range(len(instances)):
        instances[x]['Reserved'] = False
        instances[x]['AccountName'] = account_name

    reserved_for_account = get_reserved_instances(ec2)
    for x in range(len(reserved_for_account)):
        reserved_for_account[x]['AccountName'] = account_name
        
    reserved.extend(reserved_for_account)

    for x in range(len(reserved)):
        for y in range(len(instances)):
            if (reserved[x] is not None):
                if (reserved[x]['InstanceType'] == instances[y]['InstanceType']):
                    if (reserved[x]['Scope'] == 'Region' or (reserved[x]['Scope'] == 'Availability Zone' and reserved[x]['AvailabilityZone'] == instances[y]['Placement']['AvailabilityZone'])):
                        if (instances[y]['Reserved'] is False):
                            instances[y]['Reserved'] = 'True'
                            reserved[x] = None
                            continue

def load_creds():
    global creds_file

    creds = []
    tmp = ['','','']
    f = open(creds_file, 'r')
    for line in f:
        line = line.lstrip().rstrip()
        if len(line) < 2 or line[0] == '#':
            continue

        #[techonline]
        if line[0] == '[' and line[len(line)-1] == ']':
            if tmp != ['','','']:
                creds.append(tmp)
                tmp = ['','','']
            tmp[0] = line[1:len(line)-1]
        #aws_access_key_id = AAAAAAAAAAAAAAAAAAAA
        if 'aws_access_key_id' in line:
            tmp[1] = line.split('=')[1].lstrip()
        #aws_secret_access_key = AAAAAAAAAAA/AAAAAAAAAAAAAAAAAAAAAAAAAAAA
        if 'aws_secret_access_key' in line:
            tmp[2] = line.split('=')[1].lstrip()
    if tmp != ['','','']:
        creds.append(tmp)

    f.close()

    return creds

def get_running_instances(ec2, cw, display=False):
    instances = ec2.describe_instances()
    ret = []

    for r in instances['Reservations']:
        for i in r['Instances']:
            if (i['State']['Name'] == 'running'):
                cpu_load = cw.get_metric_statistics(
                    Period=3600,
                    StartTime=datetime.utcnow() - timedelta(seconds=604800),
                    EndTime=datetime.utcnow(),
                    MetricName='CPUUtilization',
                    Namespace='AWS/EC2',
                    Statistics=['Average'],
                    Dimensions=[{'Name':'InstanceId', 'Value':i['InstanceId']}]
                )
                
                load_averages = []
                for datapoint in cpu_load['Datapoints']:
                    load_averages.append(datapoint['Average'])
             
                if (len(load_averages) > 0):
                    i['CPUAvg'] = str(float(sum(load_averages))/float(len(load_averages))) + "%"
                else:
                    i['CPUAvg'] = None
                    
                ret.append(i)

                if (display is True):
                    print_instance(i)
                    print '---------'

    return ret

def get_reserved_instances(ec2, display=False):
    reserved = ec2.describe_reserved_instances()
    reserved_instances = []

    if (display is True):
        for r in reserved['ReservedInstances']:
            print_reserved_instance(r)

    for r in reserved['ReservedInstances']:
        if r['State'] == 'active':
            reserved_instances.append(r)

    return reserved_instances

def check_reservable(i):
    global suggest_reserved_threshold
    
    #launched_date = datetime(int(i['LaunchTime'][0:4]), int(i['LaunchTime'][5:7]), int(i['LaunchTime'][8:10]))
    now = datetime.now()
    elapsed_time = now - i['LaunchTime'].replace(tzinfo=None)

    if (elapsed_time.days > suggest_reserved_threshold):
        print_instance(i, 'This instance has been running on-demand for ' + str(elapsed_time.days) + ' days. Should we reserve it?')

def check_resizable(i):
    global resize_cpu_utilization_threshold, large_sizes

    if (i['CPUAvg'] is None):
        print "No CPU data available for " + str(i['InstanceId']) + ' in ' + i['AccountName']
        return

    size = i['InstanceType'].split('.')[1]
    if (size not in large_sizes):
        return

    cpu_usage = int(float(i['CPUAvg'][:len(i['CPUAvg'])-1]))
    if (cpu_usage < 1):
        print_instance(i, 'CPU Utilization is less than 1%. Can this be a smaller instance type?')
    elif (cpu_usage < resize_cpu_utilization_threshold):
        print_instance(i, 'CPU Utilization is only ' + str(cpu_usage) + '%. Can this be a smaller instance type?')

def print_instance(i, comment=''):
    #print json.dumps(i, indent=4, sort_keys=True, default=json_serial)        

    print '-------------------------------'
    print 'Account: ' + i['AccountName']
    if 'Tags' in i:
        print 'Name: ' + i['Tags'][0]['Value']
    print 'InstanceId: ' + i['InstanceId']
    print 'State: ' + i['State']['Name']
    print 'Instance Type: ' + i['InstanceType']
    print 'Availability Zone: ' + i['Placement']['AvailabilityZone']
    print 'Launched: ' + str(i['LaunchTime'])
    print 'Average CPU Utilization: ' + i['CPUAvg']
    print 'Reserved: ' + str(i['Reserved'])

    if (comment is not ''):
        print 'Comment: ' + comment

def print_reserved_instance(r):
    print 'Availability Zone: ' + r['AvailabilityZone']
    print 'Expires: ' + str(r['End'])
    print 'Upfront Price: ' + str(r['FixedPrice'])
    print 'Usage Price: ' + str(r['UsagePrice'])
    print 'Instance Type: ' + r['InstanceType']
    print 'State: ' + r['State']

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type %s not serializable" % type(obj))

if __name__ == "__main__": 
    main()
