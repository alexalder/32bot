# -*- coding: utf-8 -*-

# Base imports
import json
import logging
import urllib.request, urllib.parse, urllib.error
from datetime import datetime
import pytz
import sys
import random

from pettagram.pettagram import Bot

# App engine imports
from flask import Flask, request, make_response
from google.cloud import firestore
from google.cloud.firestore_v1beta1 import ArrayRemove, ArrayUnion

# Configuration
app = Flask(__name__)

# Database
db = firestore.Client()

secrets = db.collection('data').document('secrets').get().to_dict()


bot = Bot('https://api.telegram.org/bot' + secrets['telegram_token'] + '/')

# Logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

# Lables handling and caching
labels_chat_id = None
labels = None


# Telegram webhook handling
@app.route('/me')
def me_handler():
    return json.dumps(json.load(urllib.request.urlopen(bot.base_url + 'getMe')))


@app.route('/updates')
def updates_handler():
    return json.dumps(json.load(urllib.request.urlopen(bot.base_url + 'getUpdates')))


@app.route('/set_webhook')
def set_webhook():
    url = request.values.get('url')
    if url:
        return json.dumps(json.load(urllib.request.urlopen(
            bot.base_url + 'setWebhook', urllib.parse.urlencode({'url': url}).encode("utf-8"))))


# Messages handling
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    body = request.get_json()
    logging.info('Request body:')
    logging.info(body)

    global labels_chat_id
    global labels

    if 'callback_query' in body:
        # Callback received
        try:
            query_id = body['callback_query'].get('id')
            data = body['callback_query'].get('data')
            user_id = body['callback_query'].get('from').get('id')
            chat_id = body['callback_query'].get('message').get('chat').get('id')
            inline_message_id = body['callback_query'].get('message').get('message_id')
            if body['callback_query'].get('message').get('reply_to_message') is not None:
                reply_id = body['callback_query'].get('message').get('reply_to_message').get('message_id')
                reply_from_id = body['callback_query'].get('message').get('reply_to_message').get('from').get('id')

            if data == 'no':
                bot.delete_message(chat_id, inline_message_id)

            if data == 'yes':
                if user_id == reply_from_id or user_id == secrets['alessandro_id']:
                    photos = body['callback_query'].get('message').get('reply_to_message').get('photo')
                    if photos is not None:
                        photo_id = photos[-1].get('file_id')
                        if photo_id is not None:
                            reply_markup = {
                              'inline_keyboard': [
                                [{'text': 'Primo', 'callback_data': 'none'}, {'text': '1', 'callback_data': 'primo1'}, {'text': '2', 'callback_data': 'primo2'}, {'text': '3', 'callback_data': 'primo3'}],
                                [{'text': 'Riso', 'callback_data': 'riso'}],
                                [{'text': 'Secondo', 'callback_data': 'none'}, {'text': '1', 'callback_data': 'secondo1'}, {'text': '2', 'callback_data': 'secondo2'}],
                                [{'text': 'Contorno', 'callback_data': 'none'}, {'text': '1', 'callback_data': 'contorno1'}, {'text': '2', 'callback_data': 'contorno2'}, {'text': '3', 'callback_data': 'contorno3'}, {'text': '4', 'callback_data': 'contorno4'}],
                                [{'text': 'Non vengo', 'callback_data': 'noshow'}, {'text': 'Ordinato', 'callback_data': 'ordered'}]
                              ]
                            }
                            reply_markup = json.dumps(reply_markup)
                            post = bot.send(chat_id, msg="Menù pranzo", photo_id=photo_id, keyboard=reply_markup)
                            post_json = post.decode('utf8')
                            post_id = json.loads(post_json)['result'].get('message_id')
                            orders = bot.send(chat_id, msg="Ordinazioni:")
                            orders_json = orders.decode('utf8')
                            orders_id = json.loads(orders_json)['result'].get('message_id')
                            init_database(orders_id, chat_id)
                            bot.pin(post_id, chat_id)
                            bot.delete_message(chat_id, inline_message_id)
                            bot.delete_message(chat_id, reply_id)
            elif data == 'none':
                pass
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

                if data == 'ordered':
                    doc_ref.update({'ordered': username})

                elif data == 'noshow':
                    if username in getattr(order, data):
                        doc_ref.update({data: ArrayRemove([username])})
                    else:
                        doc_ref.update({'seats': ArrayRemove([username])})
                        for key in list(Order.default_labels.keys()):
                            doc_ref.update({key: ArrayRemove([username])})
                        doc_ref.update({data: ArrayUnion([username])})

                else:
                    if username in getattr(order, data):
                        doc_ref.update({data: ArrayRemove([username])})
                    else:
                        doc_ref.update({data: ArrayUnion([username])})
                        doc_ref.update({'seats': ArrayUnion([username])})
                        doc_ref.update({'noshow': ArrayRemove([username])})

                doc = doc_ref.get()
                order = Order.from_dict(doc.to_dict())
                bot.edit_message(chat_id, order.post_id, str(order), parse_mode="Markdown")

            return bot.answer_callback(query_id)

        except Exception as e:
            logging.info(e)
            return make_response('Error in callback handling')

    # Useful variables
    try:
        message = body['message']
    except Exception:
        if body.get('edited_message') is not None:
            message = body['edited_message']
        else:
            return json.dumps(body)

    message_id = message.get('message_id')
    text = message.get('text')
    is_forward = message.get('forward_from')
    fr = message.get('from')
    fr_id = fr.get('id')
    chat = message['chat']
    chat_id = chat['id']
    is_private_chat = (fr_id == chat_id)
    reply_message = None
    reply_text = None
    fr = message.get('from')
    if message.get('reply_to_message') is not None:
        reply_message = message.get('reply_to_message')
        if message.get('reply_to_message').get('text') is not None:
            reply_text = message.get('reply_to_message').get('text')

    if (not text) or is_forward:
        # Image received?
        timestamp = message.get('date')
        message_date = datetime.fromtimestamp(timestamp).astimezone(pytz.timezone('Europe/Rome'))
        caption = message.get('caption')
        photos = message.get('photo')
        if 11 <= message_date.hour <= 13:
            if fr_id in secrets['sender_ids']:
                if photos is not None:
                    photo_id = photos[-1].get('file_id')
                    if photo_id is not None:
                        reply_markup = {'inline_keyboard': [[{'text': 'Yes', 'callback_data': 'yes'}]]}
                        reply_markup = json.dumps(reply_markup)
                        return bot.send(chat_id, msg="Menù pranzo?", reply=message_id, keyboard=reply_markup)
        if (caption and caption == 'testphoto') and (fr_id == secrets['alexalder_id'] or fr_id == secrets['alessandro_id']):
            photo_id = photos[-1].get('file_id')
            if photo_id is not None:
                reply_markup = {'inline_keyboard': [[{'text': 'Yes', 'callback_data': 'yes'}, {'text': 'No', 'callback_data': 'no'}]]}
                reply_markup = json.dumps(reply_markup)
                return bot.send(chat_id, msg="Menù pranzo?", reply=message_id, keyboard=reply_markup)

        print('no text')
        return json.dumps(body)

    else:
        uniformed_text = text.lower()

    if text.startswith('/labels'):
        labels_chat_id = chat_id
        return bot.send(chat_id, msg="Manda la lista dei piatti, separati andando a capo (9 linee)")

    elif text.startswith('/conto'):
        return bot.send(chat_id, msg=secrets['bill_address'])

    elif text.startswith('/ping'):
        answers = ['Welo', 'Bopo']
        return bot.send(chat_id, msg=random.choice(answers))

    elif labels_chat_id == chat_id:
        lines = []
        if ';' in text:
            lines = [x.strip() for x in text.split(';')]
        else:
            lines = text.splitlines()
        if len(lines) == 9:
            doc_ref = db.collection(u'data').document(u'two')
            doc = doc_ref.get()
            dic = doc.to_dict()
            keys = list(Order.default_labels.keys())
            for i in range(9):
                dic[keys[i]] = lines[i].strip()
            dic[keys[10]] = datetime.today().day
            db.collection(u'data').document(u'two').set(dic)
            labels = None
            doc_ref = db.collection(u'data').document(u'one')
            doc = doc_ref.get()
            order = Order.from_dict(doc.to_dict())
            bot.edit_message(order.chat_id, order.post_id, str(order), parse_mode="Markdown")
            reply_markup = {
                               'inline_keyboard': [
                                 [{'text': dic['primo1'], 'callback_data': 'primo1'}], [{'text': dic['primo2'], 'callback_data': 'primo2'}], [{'text': dic['primo3'], 'callback_data': 'primo3'}],
                                 [{'text': 'Riso', 'callback_data': 'riso'}],
                                 [{'text': dic['secondo1'], 'callback_data': 'secondo1'}], [{'text': dic['secondo2'], 'callback_data': 'secondo2'}],
                                 [{'text': dic['contorno1'], 'callback_data': 'contorno1'}], [{'text': dic['contorno2'], 'callback_data': 'contorno2'}], [{'text': dic['contorno3'], 'callback_data': 'contorno3'}], [{'text': dic['contorno4'], 'callback_data': 'contorno4'}],
                                 [{'text': 'Non vengo', 'callback_data': 'noshow'}, {'text': 'Ordinato', 'callback_data': 'ordered'}]
                               ]
                            }
            reply_markup = json.dumps(reply_markup)
            bot.edit_caption(order.chat_id, order.post_id - 1, "Menù pranzo", keyboard=reply_markup)
            return bot.send(chat_id, msg="Label aggiornate")
        elif is_private_chat:
            return bot.send(chat_id, msg="Errore nella lettura, il messaggio deve avere solo 9 righe con i 9 nomi dei piatti")

    return json.dumps(body)


class Order(object):
    default_labels = {
        u'primo1': u'Primo 1',
        u'primo2': u'Primo 2',
        u'primo3': u'Primo 3',
        u'secondo1': u'Secondo 1',
        u'secondo2': u'Secondo 2',
        u'contorno1': u'Contorno 1',
        u'contorno2': u'Contorno 2',
        u'contorno3': u'Contorno 3',
        u'contorno4': u'Contorno 4',
        u'riso': u'Riso',
        u'giorno': None
    }

    def __init__(self, post_id, chat_id, noshow=[], ordered=None, seats=[], primo1=[], primo2=[], primo3=[], riso=[], secondo1=[],
                 secondo2=[], contorno1=[], contorno2=[], contorno3=[], contorno4=[]):
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
        self.chat_id = chat_id
        self.noshow = noshow
        self.ordered = ordered
        self.seats = seats

    @staticmethod
    def from_dict(source):
        order = Order(source[u'post_id'], source[u'chat_id'], source[u'noshow'], source[u'ordered'], source[u'seats'], source[u'primo1'], source[u'primo2'],
                      source[u'primo3'], source[u'riso'], source[u'secondo1'], source[u'secondo2'],
                      source[u'contorno1'], source[u'contorno2'], source[u'contorno3'], source[u'contorno4'])

        return order

    def to_dict(self):
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
            u'chat_id': self.chat_id,
            u'noshow': self.noshow,
            u'ordered': self.ordered,
            u'seats': self.seats,
        }

        return dest

    def __repr__(self):

        def get_dish(name):
            if (len(getattr(self, name)) > 0) or (labels == self.default_labels):
                return " {}: ({}) {}\n".format(get_label(name), len(getattr(self, name)), getattr(self, name))
            else:
                return ""

        def get_label(name):
            if len(getattr(self, name)) > 0:
                return "*" + labels[name] + "*"
            else:
                return labels[name]

        global labels
        if not labels or labels[u'giorno'] != datetime.today().day:
            doc_ref = db.collection(u'data').document(u'two')
            doc = doc_ref.get()
            labels = doc.to_dict()
        return(
            'Ordine:\n{}{}{}{}{}{}{}{}{}{}Persone a pranzo: {} {}\nNon vengono: {}\n{}'
            .format(get_dish('primo1'),
                    get_dish('primo2'),
                    get_dish('primo3'),
                    get_dish('riso'),
                    get_dish('secondo1'),
                    get_dish('secondo2'),
                    get_dish('contorno1'),
                    get_dish('contorno2'),
                    get_dish('contorno3'),
                    get_dish('contorno4'),
                    len(self.seats), self.seats,
                    self.noshow,
                    ("ORDINATO ✅" + " (" + self.ordered + ")") if self.ordered else "NON ANCORA ORDINATO")
            .replace("'", ""))


def init_database(post_id, chat_id):
    global labels
    db.collection(u'data').document(u'one').set(Order(post_id, chat_id).to_dict())
    db.collection(u'data').document(u'two').set(Order.default_labels)
    labels = None
