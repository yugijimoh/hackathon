"""
Lex - db and ML 
"""

import json
import datetime
import time
import os
import dateutil.parser
import logging

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


# --- Helpers that build all of the responses ---


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


# --- Helper Functions ---


def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(n)
    return n


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None



def checkticket(intent_request):
    slots = intent_request['currentIntent']['slots']
    ticketnumber = slots['ticketnumber']
    logger.debug('ticketnumber:{}'.format(ticketnumber))
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    logger.debug('here to check with maching learning for ticket:{}'.format(ticketnumber))

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('incidentDummy_v2')
    items = table.query(KeyConditionExpression=Key('IncidentNumber').eq(ticketnumber))
    client = boto3.client('machinelearning')
    if(items is None):
        return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Ticket: {0} not exist in DB yet, please try another one.'.format(ticketnumber)
        }
    )
    response = client.predict(
        #MLModelId="ml-t0gvKoYGz6d",
        MLModelId="ml-cm2S9nNwk3e",
        Record={
            "IncidentNumber": items["Items"][0]["IncidentNumber"],
            "AffectedEndUser": items["Items"][0]["AffectedEndUser"],
            "CI": items["Items"][0]["CI"],
            "Summary": items["Items"][0]["Summary"]
            #"id": items["Items"][0]["id"]
        },
        PredictEndpoint="https://realtime.machinelearning.us-east-1.amazonaws.com"
    )
    
    logger.debug(response)
    priority = response['Prediction']['predictedLabel']
    flag = ''
    if priority=='1':
        flag = 'It should be an TOP URGENT case!! PLEASE TAKE ACTION AT YOUR SOONEST!!'
    elif priority=='2':
        flag = 'It should be an URGENT case!! Please take action ASAP!'
    elif priority=='3':
        flag = 'It should be an Normal case! Please take action in 8 hours.'    
    else :
        flag = 'It should be an Normal case. Please take action by today.'
            
    rst = response['Prediction']['predictedScores']
    pscore=''
    for p,score in rst.iteritems():
        if(p==priority):
            pscore=score
            
    pscore=round(pscore*100,2)
    session_attributes['Ticket number'] = ticketnumber
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'I think ticket: {0} is a Priority{1} case. Predicted posibility: {2}%. \r{3}'.format(ticketnumber,priority,pscore,flag)
        }
    )
    
    
def checkWIKI(intent_request):
    slots = intent_request['currentIntent']['slots']
    question = slots['question']
    logger.debug('question:{}'.format(question))
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    logger.debug('here to looking for solution for question:{}'.format(question))

    client = boto3.client('machinelearning')
    response = client.predict(
        MLModelId="ml-ocBazIoXjMv",
        Record={
            "Summary": question
        },
        PredictEndpoint="https://realtime.machinelearning.us-east-1.amazonaws.com"
    )
    
    logger.debug(response)
    flag = response['Prediction']['predictedLabel']
    if flag=='none':
        result = 'sorry, cannot find a solution for your question at the monment, please contact our local IT ext:89999'
    else:
        result = 'here is the solution for your reference: ' + flag
        
    session_attributes['solution'] = flag
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': result
        }
    )


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug(
        'dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'checkticket':
        return checkticket(intent_request)
    elif intent_name == 'checkWIKI':
        return checkWIKI(intent_request)
    else:
        raise Exception('Intent with name ' + intent_name + ' not supported')


# --- Main handler ---


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
