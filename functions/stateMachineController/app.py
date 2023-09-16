#lambda function to start a given state machine
import json
import boto3
import datetime
import os

SM_ARN = os.getenv("STATEMACHINE_ARN")
sm = boto3.client('stepfunctions')

def lambda_handler(event, context):
    sm_already_running = len(sm.list_executions(
        stateMachineArn = SM_ARN,
        statusFilter = 'RUNNING'
    )['executions']) > 0

    #response object
    response = {
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST'
            },
            'isBase64Encoded': False
            }
    

    if sm_already_running:
        response['statusCode'] = 403
        response['body'] = json.dumps({'message':'recovery job already running'})
        
    else:
        #start state machine execution with name 'Orchestrator-poc-<date>-time' 
        execution = sm.start_execution(
            stateMachineArn = SM_ARN,
            name = "Orchestrator-poc-{}".format(datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
        )
        #return http 201 with message 'started'
        response['statusCode'] = 201
        response['body'] = json.dumps({'message':'job started'})
        
    return response