import boto3
import logging
from pprint import pprint

drs = boto3.client('drs')
logger = logging.Logger(logging.INFO)

def lambda_handler(event, context):
    pprint(event)

    #wave number, from state machine. If not passed in, assume 1
    wave = event.get('wave') if event.get('wave') is not None else 1
    #event status, from state machine. If not passed in, assume started
    current_status = event.get('status') if event.get('status') is not None else 'start'
    #jobid, from state machine. If not passed in, assume empty
    jobid = event.get('jobid') if event.get('jobid') is not None else ''
    #total waves. If not passed in, assume 0
    total_waves = event.get('total_waves') if event.get('total_waves') is not None else 0

    #retrieve the server list and sort the list by wave
    serverList = get_source_servers()
    
    #get the number of waves
    total_waves = serverList[-1]['wave']

    #switch case current status to determine the next action to take
    match current_status:
        case 'start':
            return start_recovery(serverList, wave, total_waves)
        case 'running':
            return check_wave_status(wave, jobid, total_waves)
        case 'finished':
            #if the wave is the last wave, return finished
            if wave == total_waves:
                return {"status": "done", "wave": wave, "total_waves": total_waves}
            else:
                #if not, start the next wave
                wave += 1
                return start_recovery(serverList, wave, total_waves)

#retrive a list of source servers from DRS, sorted by wave number
def get_source_servers():
    #Describe all source servers
    paginator = drs.get_paginator('describe_source_servers')
    response_iterator = paginator.paginate(
        filters={},
        maxResults = 200,
        PaginationConfig={
            'MaxItems' : 200,
            'PageSize' : 200
        }
    )
    
    #Make a list of all source server IDs
    serverItems = []
    for i in response_iterator:
        serverItems += i.get('items')
    serverList = []
    for i in serverItems:
        serverList.append({"wave":int(i['tags']['wave']), "sourceServerID":i['sourceServerID']})
    
    #sort the list by wave number, ascending
    serverList.sort(key=lambda k: k['wave'])

    return serverList

#start a failover of all source servers in a given wave
def start_recovery(serverList, wave, total_waves):
    #get the list of source servers in the given wave
    wave_servers = []
    for i in serverList:
        if i['wave'] == wave:
            wave_servers.append({'sourceServerID': i['sourceServerID']})
    
    logger.info("wave: {}".format(wave))
    logger.info("wave_servers: {}".format(wave_servers))

    #check if there are any source servers in the given wave. If not, return finished
    if wave_servers == []:
        return {"status": "finished", "wave": wave, "total_waves": total_waves}
    #if there are source servers, start failover
    else:
        failover = drs.start_recovery(
            isDrill=True,
            sourceServers=wave_servers
        ),
        tags = {
            'wave': wave
        }
        #retrieve the jobid
        jobid = failover[0]['job']['jobID']
        
    logger.info("failing over {} servers in wave {}".format(len(wave_servers), wave))
    return {"status": "running", "wave": wave, "jobid": jobid, "total_waves": total_waves}

#check the status of a given jobid
def check_wave_status(wave, jobid, total_waves):
    #check the status of the given jobid
    status = drs.describe_jobs(
        filters={
            'jobIDs': [jobid]
        }
    )['items'][0].get('status')

    #if the job is finished, return finished
    if status == 'COMPLETED':
        return {"status": "finished", "jobid": jobid, "wave": wave, "total_waves": total_waves}
    #if the job is still running, return running
    elif status == 'STARTED':
        return {"status": "running", "jobid": jobid, "wave": wave, "total_waves": total_waves}
    #if the job is not finished or running, return error
    else:
        return {"status": "error", "jobid": jobid, "wave": wave, "total_waves": total_waves}