# aws-cost-optimization

This is a script for generating reports on AWS usage that can be used for cost optimization.

Flags are currently configurable as global variables:

print_all  
print all instance information, regardless of whether or not any changes are needed

show_unused_reserved  
print a list of reserved instances that currently do not match any active instances

suggest_reserved  
print a list of suggestions for instances to reserve
if an on-demand instance has been running for more than suggest_reserved_threshold days, it will show up here

suggest_resize  
print a list of instances that are candidates for resizing
if any instance is of a type in the large_sizes list and has had average cpu utilization less than resize_cpu_utlization_threshold over the past week, it will show up here.

This script relies on a credentials file that contains one or more account configurations in the format:  
  
[account_name_one]  
aws_access_key_id = XXXXXXXX  
aws_secret_access_key = XXXXXXXX  

This file will be automatically generated when the AWS CLI is installed and configured.
