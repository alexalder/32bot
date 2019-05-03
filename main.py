# -*- coding: utf-8 -*-

# Base imports
import json
import logging
import urllib.request, urllib.parse, urllib.error
from datetime import datetime
import sys
import requests
import random

# App engine imports
from flask import Flask, request, make_response
from google.cloud import firestore
from google.cloud.firestore_v1beta1 import ArrayRemove, ArrayUnion

import secrets

# Configuration
app = Flask(__name__)

# Project ID is determined by the GCLOUD_PROJECT environment variable
db = firestore.Client()

BASE_URL = 'https://api.telegram.org/bot' + secrets.telegram_token + '/'

# Logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

# Telegram webhook handling
@app.route('/me')
def me_handler():
    return json.dumps(json.load(urllib.request.urlopen(BASE_URL + 'getMe')))


@app.route('/updates')
def updates_handler():
    return json.dumps(json.load(urllib.request.urlopen(BASE_URL + 'getUpdates')))


@app.route('/set_webhook')
def set_webhook():
    url = request.values.get('url')
    if url:
        return json.dumps(json.load(urllib.request.urlopen(
            BASE_URL + 'setWebhook', urllib.parse.urlencode({'url': url}).encode("utf-8"))))

# Returns the sent message as JSON
def send(msg, chat_id, reply=None, keyboard=json.dumps({'inline_keyboard': [[]]})):
    try:
        resp = urllib.request.urlopen(BASE_URL + 'sendMessage', urllib.parse.urlencode({
                'chat_id': str(chat_id),
                'text': msg.encode('utf-8'),
                'parse_mode': 'HTML',
                'disable_web_page_preview': 'true',
                'reply_to_message_id': reply,
                'reply_markup': keyboard,
            }).encode("utf-8")).read()
        logging.info(resp)
    except Exception:
        resp = make_response('Error in send')
    return resp

def sendphoto(msg, file_id, chat_id, reply=None, keyboard=json.dumps({'inline_keyboard': [[]]})):
    try:
        resp = urllib.request.urlopen(BASE_URL + 'sendPhoto', urllib.parse.urlencode({
            'chat_id': str(chat_id),
            'photo': file_id,
            'caption': msg.encode('utf-8'),
            'parse_mode': 'Markdown',
            'reply_to_message_id': str(reply),
            'reply_markup': keyboard,
        }).encode("utf-8")).read()
        logging.info(resp)
    except Exception as e:
        resp = make_response('Error in sendphoto')
    finally:
        return resp

def editmessage(chat_id, message_id, text):
    try:
        resp = urllib.request.urlopen(BASE_URL + 'editMessageText', urllib.parse.urlencode({
                'chat_id': str(chat_id),
                'message_id': int(message_id),
                'text': text.encode('utf-8'),
                'parse_mode': 'HTML',
                'disable_web_page_preview': 'true',
            }).encode("utf-8")).read()
        logging.info(resp)
    except Exception:
        resp = make_response('Error in edit')
    return resp

def answer_callback(query_id):
    try:
        resp = urllib.request.urlopen(BASE_URL + 'answerCallbackQuery', urllib.parse.urlencode({
                'callback_query_id': query_id,
            }).encode("utf-8")).read()
    except Exception:
        resp = make_response('Error in callbackanswer')
    finally:
        return resp

def pin(message_id, chat_id, notification=True):
    try:
        res = urllib.request.urlopen(BASE_URL + 'pinChatMessage', urllib.parse.urlencode({
            'chat_id': str(chat_id),
            'message_id': int(message_id),
            'disable_notification': not notification, }).encode("utf-8")).read()
        return res
    except Exception:
        return make_response('Error in pin')

# Messages handling
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    body = request.get_json()
    logging.info('Request body:')
    logging.info(body)

    if ('callback_query' in body):
        #Callback received
        try:
            query_id = body['callback_query'].get('id')
            data = body['callback_query'].get('data')
            user_id = body['callback_query'].get('from').get('id')
            chat_id = body['callback_query'].get('message').get('chat').get('id')
            inline_message_id = body['callback_query'].get('message').get('message_id')

            if data == 'yes':
                if user_id == body['callback_query'].get('message').get('reply_to_message').get('from').get('id') or user_id == secrets.alessandro_id:
                    photos = body['callback_query'].get('message').get('reply_to_message').get('photo')
                    if photos is not None:
                        photo_id = photos[-1].get('file_id')
                        if photo_id is not None:
                            reply_markup = {'inline_keyboard': [[{'text': 'Primo 1', 'callback_data': 'primo1'},{'text': '2', 'callback_data': 'primo2'},{'text': '3', 'callback_data': 'primo3'}],[{'text': 'Riso', 'callback_data': 'riso'},{'text': 'Secondo 1', 'callback_data': 'secondo1'},{'text': '2', 'callback_data': 'secondo2'}],[{'text': 'Contorno 1', 'callback_data': 'contorno1'},{'text': '2', 'callback_data': 'contorno2'},{'text': '3', 'callback_data': 'contorno3'},{'text': '4', 'callback_data': 'contorno4'}]]}
                            reply_markup = json.dumps(reply_markup)
                            post = sendphoto("Menù pranzo", photo_id, chat_id, keyboard=reply_markup)
                            post_json = post.decode('utf8')
                            post_id = json.loads(post_json)['result'].get('message_id')
                            ordinazioni = send("Ordinazioni:", chat_id)
                            ordinazioni_json = ordinazioni.decode('utf8')
                            ordinazioni_id = json.loads(ordinazioni_json)['result'].get('message_id')
                            init_database(ordinazioni_id)
                            pin(post_id, chat_id)
            
            else:
                doc_ref = db.collection(u'data').document(u'one')
                doc = doc_ref.get()
                order = Order.from_dict(doc.to_dict())

                if body['callback_query'].get('from').get('first_name') is not None:
                    username = body['callback_query'].get('from').get('first_name')
                elif body['callback_query'].get('from').get('username') is not None:
                    username = body['callback_query'].get('from').get('username')
                else:
                    username = body['callback_query'].get('from').get('id')

                if username in getattr(order, data):
                    doc_ref.update({data: ArrayRemove([username])})
                else:
                    doc_ref.update({data: ArrayUnion([username])})

                doc = doc_ref.get()
                order = Order.from_dict(doc.to_dict())
                editmessage(chat_id, order.post_id, str(order))

            return answer_callback(query_id)

        except Exception as e:
            logging.info(e)
            return make_response('Error in callback handling')

    try:
        message = body['message']
    except Exception:
        message = body['edited_message']
    message_id = message.get('message_id')
    text = message.get('text')
    is_forward = message.get('forward_from')
    fr = message.get('from')
    fr_id = fr.get('id')
    chat = message['chat']
    chat_id = chat['id']
    reply_message = None
    reply_text = None
    fr = message.get('from')
    if message.get('reply_to_message') is not None:
        reply_message = message.get('reply_to_message')
        if message.get('reply_to_message').get('text') is not None:
            reply_text = message.get('reply_to_message').get('text')

    if (not text) or is_forward:
        #Image received?
        timestamp = message.get('date')
        message_date = datetime.fromtimestamp(timestamp)
        caption = message.get('caption')
        photos = message.get('photo')
        if 11 <= message_date.hour <= 13:
            if fr_id == secrets.massimo_id or fr_id == secrets.roberta_id:
                if photos is not None:
                    photo_id = photos[-1].get('file_id')
                    if photo_id is not None:
                        reply_markup = {'inline_keyboard': [[{'text': 'Yes', 'callback_data': 'yes'}]]}
                        reply_markup = json.dumps(reply_markup)
                        return send("Menù pranzo?", chat_id, reply=message_id, keyboard=reply_markup)
        if (caption is not None and caption == 'testphoto') and (fr_id == secrets.alexalder_id or fr_id == secrets.alessandro_id):
            photo_id = photos[-1].get('file_id')
            if photo_id is not None:
                reply_markup = {'inline_keyboard': [[{'text': 'Yes', 'callback_data': 'yes'}]]}
                reply_markup = json.dumps(reply_markup)
                return send("Menù pranzo?", chat_id, reply=message_id, keyboard=reply_markup)

        logging.info('no text')
        return json.dumps(body)

    if text.startswith('/conto'):
        return send(secrets.bill_address, chat_id)

    if text.startswith('/ping'):
        answers = ['Welo', 'Bopo']
        return send(random.choice(answers), chat_id)

    return json.dumps(body)

    # Useful variables
    uniformed_text = text.lower()

# [START custom_class_def]
class Order(object):
    def __init__(self, post_id, primo1 = [], primo2 = [], primo3 = [], riso = [], secondo1 = [], secondo2 = [], contorno1 = [], contorno2 = [], contorno3 = [], contorno4 = []):
        self.primo1 = primo1
        self.primo2 = primo2
        self.primo3 = primo3
        self.riso = riso
        self.secondo1 = secondo1
        self.secondo2 = secondo2
        self.contorno1 = contorno1
        self.contorno2 = contorno2
        self.contorno3 = contorno3
        self.contorno4 = contorno4
        self.post_id = post_id

    @staticmethod
    def from_dict(source):
        # [START_EXCLUDE]
        order = Order(source[u'post_id'], source[u'primo1'], source[u'primo2'], source[u'primo3'], source[u'riso'], source[u'secondo1'], source[u'secondo2'], source[u'contorno1'], source[u'contorno2'], source[u'contorno3'], source[u'contorno4'])

        return order
        # [END_EXCLUDE]

    def to_dict(self):
        # [START_EXCLUDE]
        dest = {
            u'primo1': self.primo1,
            u'primo2': self.primo2,
            u'primo3': self.primo3,
            u'riso': self.riso,
            u'secondo1': self.secondo1,
            u'secondo2': self.secondo2,
            u'contorno1': self.contorno1,
            u'contorno2': self.contorno2,
            u'contorno3': self.contorno3,
            u'contorno4': self.contorno4,
            u'post_id': self.post_id,
        }

        return dest
        # [END_EXCLUDE]

    def __repr__(self):
        return(
            'Ordine:\n Primo 1: ({}) {}\n Primo 2: ({}) {}\n Primo 3: ({}) {}\n Riso: ({}) {}\n Secondo 1: ({}) {}\n Secondo 2: ({}) {}\n Contorno 1: ({}) {}\n Contorno 2: ({}) {}\n Contorno 3: ({}) {}\n Contorno 4: ({}) {}'
            .format(len(self.primo1), self.primo1, len(self.primo2), self.primo2, len(self.primo3), self.primo3, len(self.riso), self.riso, 
                    len(self.secondo1), self.secondo1, len(self.secondo2), self.secondo2, len(self.contorno1), self.contorno1, len(self.contorno2), self.contorno2, len(self.contorno3), self.contorno3, len(self.contorno4), self.contorno4)
            .replace("'", ""))

# [END custom_class_def]

def init_database(post_id):
    db.collection(u'data').document(u'one').set(Order(post_id).to_dict())
