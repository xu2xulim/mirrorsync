from typing import Optional
from fastapi import FastAPI, Body, status
from starlette.requests import Request
from fastapi.responses import JSONResponse

import os
from pydantic import BaseModel
from deta import Deta
from datetime import datetime
from dateutil.parser import parse
from trello import TrelloClient, List
import urllib.request

app = FastAPI(title="MirrorSync", version="1.0")
lookup = Deta().Base('mirrorsync_lookup')

TRELLO_API_KEY = os.environ.get('TRELLO_API_KEY')
TRELLO_TOKEN = os.environ.get('TRELLO_TOKEN')
INSTANCE_HOSTNAME=os.environ.get('INSTANCE_HOSTNAME')

MS_CONFIG = {}
for k, v in os.environ.items():
    if 'MS_' in k:
        MS_CONFIG[k]=v

def trello_client():
    client = TrelloClient(
        api_key = TRELLO_API_KEY,
        token = TRELLO_TOKEN,
        )
    mbr_id = client.fetch_json('members/me')['id']
    return (client, mbr_id)

def create_webhook(card_id, alt_card_id):

    (client, me) = trello_client()
    existing_hooks = []
    for hook in client.list_hooks(token=TRELLO_TOKEN):
        if f"https://{INSTANCE_HOSTNAME}" in hook.callback_url:
            existing_hooks.append(hook.id_model)

    card_found = next((idm for idm in existing_hooks if idm == card_id), None)
    alt_found = next((idm for idm in existing_hooks if idm == alt_card_id), None)

    if card_found == None:
        wh = client.create_hook(callback_url=f"https://{INSTANCE_HOSTNAME}/mirrorsync",
                                id_model=card_id, desc="Card {} is a source card".format(card_id),
                                token=TRELLO_TOKEN)
    if alt_found == None:
        wh = client.create_hook(callback_url=f"https://{INSTANCE_HOSTNAME}/mirrorsync",
                                id_model=alt_card_id, desc="Card {} is a source card".format(alt_card_id),
                                token=TRELLO_TOKEN)

    return

async def dl (url) :

    request = urllib.request.Request(url)
    request.add_header('Authorization', '''OAuth oauth_consumer_key="{}", oauth_token="{}"'''.format(TRELLO_API_KEY, TRELLO_TOKEN))
    webUrl  = urllib.request.urlopen(request)

    data = webUrl.read()
    return data

async def labels(client, data, card_id, alt_card_id, action):

    for lbl in client.get_board(data['board']['id']).get_labels():
        if lbl.name == data['text']:
            if 'value' in data.keys():
                if lbl.color == data['value'] :
                    break
            else:
                break

    target_card = client.get_card(alt_card_id)

    if  action == 'removeLabelFromCard' :
        for t_lbl in target_card.labels:
            if t_lbl.name == data['text']:
                if 'value' in data.keys():
                    if t_lbl.color == data['value'] :
                        target_card.remove_label(t_lbl)
                    else:
                        pass
                else:
                    target_card.remove_label(t_lbl)
    else:
        if  action == 'addLabelToCard' :
            found = False
            for t_lbl in target_card.labels:
                if t_lbl.name == data['text']:
                    if 'value' in data.keys():
                        if t_lbl.color == data['value'] :
                            found = True
                        else:
                            pass
                    else:
                        found = True

            if found == False :
                target_card.create_label(name=lbl.name, color = lbl.color)
    return

async def checklists(client, data, card_id, alt_card_id, action):

    for chklst in client.get_card(card_id).checklists:
        if chklst.name == data['checklist']['name'] :
            break

    target_card = client.get_card(alt_card_id)

    found = False

    if  action == 'removeChecklistFromCard' :
        for t_cl in target_card.checklists:
            if t_cl.name == data['checklist']['name']:
                t_cl.delete()
                break

    if  action == 'addChecklistToCard' :
        for t_cl in target_card.checklists:
            if t_cl.name == data['checklist']['name']:
                found = True
                break
        if found == False :
            if len(chklst.items) == 0 :
                target_card.add_checklist(title=data['checklist']['name'], items=[])
            else:
                target_card.add_checklist(title=data['checklist']['name'],
                                          items=[d['name'] for d in  chklst.items  if 'name' in d],
                                          itemstates=None)

    if action == 'createCheckItem' :
        for t_cl in target_card.checklists:
            if t_cl.name == data['checklist']['name']:
                for itm in t_cl.items:
                    if itm['name'] == data['checkItem']['name'] :
                        found = True
                        break
        if found == False:
            t_cl.add_checklist_item(name=data['checkItem']['name'], checked=False)

    if action == 'deleteCheckItem' :
        for t_cl in target_card.checklists:
            if t_cl.name == data['checklist']['name']:
                for itm in t_cl.items:
                    if itm['name'] == data['checkItem']['name'] :
                        t_cl.delete_checklist_item(name =  data['checkItem']['name'])
                        break

    if action == 'updateCheckItemStateOnCard' :
        for t_cl in target_card.checklists:
            if t_cl.name == data['checklist']['name']:
            
                for itm in t_cl.items:
                    if itm['name'] == data['checkItem']['name'] :
                        if itm['state'] == data['checkItem']['state'] :
                            
                            break
                        else:
                            checked = False
                            if data['checkItem']['state'] == 'complete' :
                                checked = True
                            
                            t_cl.set_checklist_item(name =  data['checkItem']['name'], checked=checked)
                            break

    if action == 'updateChecklist' :
        for t_cl in target_card.checklists:
            if t_cl.name == data['old']['name']:
                t_cl.rename(new_name = data['checklist']['name'] )
                break

    if action == 'updateCheckItem' :
        for t_cl in target_card.checklists:
            if t_cl.name == data['checklist']['name']:
                for itm in t_cl.items:
                    if itm['name'] == data['old']['name'] :
                        t_cl.rename_checklist_item(name=data['old']['name'], new_name = data['checkItem']['name'])
                        break
                break

    if action == 'updateMemberOnCheckItem' :
        for t_cl in target_card.checklists:
            if t_cl.name == data['checklist']['name']:
                for itm in t_cl.items:
                    if itm['name'] == data['checkItem']['name'] and itm['idMember'] == data['old']['idMember']:
                        if data['checkItem']['idMember'] == None:
                            test_check = client.fetch_json('/cards/' + t_cl.trello_card +
                                '/checklist/' + t_cl.id +
                                '/checkItem/' + itm['id'],
                                http_method='PUT',
                                post_args={'idMember': ''})
                        else:
                            for mbr in client.get_board(target_card.board_id).all_members():
                                if mbr.id == data['checkItem']['idMember']:
                                    t_cl.set_checklist_item_member(itm, mbr)
                                    break
                        break
                break

    if action == 'updateCheckItemDue' :
        for t_cl in target_card.checklists:
            if t_cl.name == data['checklist']['name']:
                for itm in t_cl.items:
                    if itm['name'] == data['checkItem']['name'] and itm['due'] == data['old']['due'] :
                        if data['checkItem']['due'] == None:
                            test_check = client.fetch_json('/cards/' + t_cl.trello_card +
                                '/checklist/' + t_cl.id +
                                '/checkItem/' + itm['id'],
                                http_method='PUT',
                                post_args={'due': ''})
                        else:
                            t_cl.set_checklist_item_due(itm, parse(data['checkItem']['due']))
                        break
                break
    return

async def customfields(client, data, card_id, alt_card_id, action):

    target_card = client.get_card(alt_card_id)
    cfd_list = client.get_board(target_card.board_id).get_custom_field_definitions()

    field_match = next((cfd for cfd in cfd_list if cfd.name == data['customField']['name']), None)
    if field_match:
        pass
    else:
        return
    
    cf_lookup = {}
    for cfd in cfd_list:
        cf_lookup[cfd.name] = cfd

    found = False
    if  'customFieldItem' in data.keys() :

        if data['customField']['type'] == 'text':

            if target_card.get_custom_field_by_name(data['customField']['name']).value == data['customFieldItem']['value']['text'] :
                pass
            else:
                target_card.set_custom_field(value=data['customFieldItem']['value']['text'], custom_field=cf_lookup[data['customField']['name']])

        if data['customField']['type'] == 'checkbox':

            test_state = False
            user_state = 'false'
            if data['customFieldItem']['value'] == None :
                pass
            else:
                if data['customFieldItem']['value']['checked'] == 'true' :
                    test_state = True
                    user_state = 'true'

            if target_card.get_custom_field_by_name(data['customField']['name']).value == test_state :
                pass
            else:
                # error in set_custom_field for checkbox
                #target_card.set_custom_field(value=user_state, custom_field=cf_lookup[data['customField']['name']])
                post_args = {'value': {'checked': user_state}}
                client.fetch_json('/card/' + target_card.id + '/customField/' + cf_lookup[data['customField']['name']].id + '/item',
                    http_method='PUT', post_args=post_args)

        if data['customField']['type'] == 'date':
            if data['customFieldItem']['value'] == None:
                if target_card.get_custom_field_by_name(data['customField']['name']).value == data['old']['value']['date'] :
                    target_card.set_custom_field(value="", custom_field=cf_lookup[data['customField']['name']])
                #else:
                    #target_card.set_custom_field(value=data['customFieldItem']['value']['date'], custom_field=cf_lookup[data['customField']['name']])
            else:
                if data['old']['value'] == None:
                    if target_card.get_custom_field_by_name(data['customField']['name']).value == data['old']['value'] :
                        pass
                    else:
                        target_card.set_custom_field(value=data['customFieldItem']['value']['date'], custom_field=cf_lookup[data['customField']['name']])
                else:
                    if data['old']['value']['date'] != data['customFieldItem']['value']['date'] :
                        if target_card.get_custom_field_by_name(data['customField']['name']).value == data['old']['value']['date'] :
                            target_card.set_custom_field(value=data['customFieldItem']['value']['date'], custom_field=cf_lookup[data['customField']['name']])




        if data['customField']['type'] == 'number':

            if data['customFieldItem']['value'] == None :
                pass
            else:
            
                if target_card.get_custom_field_by_name(data['customField']['name']).value == float(data['customFieldItem']['value']['number']) :
                    pass
                else:
                    target_card.set_custom_field(value=data['customFieldItem']['value']['number'], custom_field=cf_lookup[data['customField']['name']])

        if data['customField']['type'] == 'list':
            list_options = cf_lookup[data['customField']['name']].list_options
            
            card = client.get_card(card_id)
            tgt_idValue = next((x for x in list_options.keys() if list_options[x] ==  card.get_custom_field_by_name(data['customField']['name']).value), None)
            
            if data['customFieldItem']['idValue'] == None and target_card.get_custom_field_by_name(data['customField']['name']).value == None:
                pass
            elif data['customFieldItem']['idValue'] == None and target_card.get_custom_field_by_name(data['customField']['name']).value != None:
                target_card.set_custom_field(value="", custom_field=cf_lookup[data['customField']['name']])
            elif tgt_idValue:
                if target_card.get_custom_field_by_name(data['customField']['name']).value == list_options[tgt_idValue] :
                    pass
                else:
                    target_card.set_custom_field(value=list_options[tgt_idValue], custom_field=cf_lookup[data['customField']['name']])
    return

async def dates(client, data, card_id, alt_card_id, action):
    target_card = client.get_card(alt_card_id)

    if  'dueComplete' in data['card'].keys() :
        if target_card.is_due_complete == data['card']['dueComplete'] :
            pass
        else:
            target_card._set_remote_attribute('dueComplete', data['card']['dueComplete'])


    if  'due' in data['card'].keys() :
        if target_card.due == data['card']['due'] :
            pass
        else:
            target_card._set_remote_attribute('due', data['card']['due'])

    if  'start' in data['card'].keys() :
        start_date = client.fetch_json('/cards/' + target_card.id + '/' + 'start', http_method='GET')['_value']
    
        if start_date == data['card']['start'] :
            pass
        else:
            if data['card']['start'] == None:
                target_card._set_remote_attribute('start', data['card']['start'])
            else:
                start_dt = parse(data['card']['start'])
                target_card.set_start(start=start_dt)

    if  'dueReminder' in data['card'].keys() :
        dueReminder = client.fetch_json('/cards/' + target_card.id + '/' + 'dueReminder', http_method='GET')['_value']
        
        if dueReminder == data['card']['dueReminder'] :
            pass
        else:
            if data['card']['dueReminder'] == None:
                target_card._set_remote_attribute('dueReminder', data['card']['dueReminder'])
            else:

                target_card.set_reminder(reminder=data['card']['dueReminder'])

    return

async def attachments(client, data, card_id, alt_card_id, action):

    for attach in client.get_card(card_id).attachments:
        if attach['name'] == data['attachment']['name'] :
            break

    target_card = client.get_card(alt_card_id)

    found = False

    if  action == 'deleteAttachmentFromCard' :

        if target_card.attachments == []:
            pass
        else:

            for t_attach in target_card.attachments:

                if t_attach['name'] == data['attachment']['name']:

                    target_card.remove_attachment(t_attach['id'])
                    break


    if  action == 'addAttachmentToCard' :

        found = False
        if target_card.attachments == []:
            pass
        else:
            for t_attach in target_card.attachments:
                ll= len("https://trello.com/b/fq13TMs8/")
                if t_attach['name'] == data['attachment']['name'] or (t_attach['name'][0:ll] == data['attachment']['name'][0:ll] and ('/c/' in data['attachment']['name'][0:ll] or '/b/' in data['attachment']['name'][0:ll])):

                    found = True
                    break

        if found == False :
            url = data['attachment']['url']
            local_filename = data['attachment']['name']
            if 'attachments' in url or 'download' in url:
                file = await dl(data['attachment']['url'])
                target_card.attach(name=local_filename, file = file)
            else:
                target_card.attach(name=local_filename, url = url )

    return

async def name (client, data, card_id, alt_card_id, action):
    target_card = client.get_card(alt_card_id)

    if target_card.name == data['card']['name'] :
        pass
    else:
        target_card.set_name(new_name=data['card']['name'])

    return

async def desc (client, data, card_id, alt_card_id, action):
    target_card = client.get_card(alt_card_id)

    if target_card.desc == data['card']['desc'] :
        pass
    else:
        target_card.set_description(description=data['card']['desc'])

    return

async def location (client, data, card_id, alt_card_id, action):
    target_card = client.get_card(alt_card_id)

    if 'address' in data['old'].keys():
        target_address = client.fetch_json('/cards/' + target_card.id + '/' + 'address', http_method='GET')['_value']
        if target_address == data['card']['address'] :
            pass
        else:
            card = client.get_card(card_id)
            from_locationName = client.fetch_json('/cards/' + card.id + '/' + 'locationName', http_method='GET')['_value']
            from_coordinates = client.fetch_json('/cards/' + card.id + '/' + 'coordinates', http_method='GET')
            target_card._set_remote_attribute('address', data['card']['address'])
            target_card._set_remote_attribute('locationName', from_locationName)
            target_card._set_remote_attribute('coordinates', from_coordinates)
    elif 'locationName' in data['old'].keys():
        target_locationName = client.fetch_json('/cards/' + target_card.id + '/' + 'locationName', http_method='GET')['_value']
        if target_locationName == data['card']['locationName'] :
            pass
        else:
            if data['card']['locationName'] == '':
                target_card._set_remote_attribute('address', '')
                target_card._set_remote_attribute('locationName', '')
                target_card._set_remote_attribute('coordinates', '')
            else:
                card = client.get_card(card_id)
                from_address = client.fetch_json('/cards/' + card.id + '/' + 'address', http_method='GET')['_value']
                from_coordinates = client.fetch_json('/cards/' + card.id + '/' + 'coordinates', http_method='GET')
                target_card._set_remote_attribute('address', from_address)
                target_card._set_remote_attribute('locationName', data['card']['locationName'])
                target_card._set_remote_attribute('coordinates', from_coordinates)


    return

def locate_comment(comments, text) :

    for com in comments :
        if com['type'] == 'commentCard' and  text == com['data']['text'].split('¿¿')[-1].strip() :
            return (True, com)

    return (False, None)

async def comments (client, data, card_id, alt_card_id, action, me, comm_writer_id, isPrimary):
    target_card = client.get_card(alt_card_id)
    comments = target_card.comments
    comments.reverse()

    comm_writer = client.get_member(comm_writer_id)

    if action == 'commentCard' :
        if isPrimary :
            if '::' not in data['text'] :
                if comm_writer_id == me:
                    target_card.comment(comment_text=data['text'])
                else:
                    target_card.comment(comment_text="{}:: {}".format(comm_writer.full_name, data['text']))

        else:
            if '::' in data['text'] :
                pass
            else:
                if comm_writer_id == me :
                    pass
                else:
                    target_card.comment(comment_text="{}:: {}".format(comm_writer.full_name, data['text']))

        """
        (found, com) = locate_comment(comments, data['text'])
        if found:
            pass
        else:
            if comm_writer_id == me :
                if '¿¿' in data['text']:
                    pass
                else:
                    target_card.comment(comment_text=data['text'])
            else:
                target_card.comment(comment_text="¿¿{}¿¿ {}".format(comm_writer.full_name, data['text']))
        """

    elif  action == 'updateComment':
        if '**del**' in data['action']['text']:
            delete_comments.put({'comment_text' : data['action']['text']}, card_id, expire_in=90)

        if 'old' in data.keys():
            if comm_writer_id != me:
                new_text = "{}:: {}".format(comm_writer.full_name, data['old']['text'])
            else:
                new_text = data['old']['text']

            found = False
            (found, com) = locate_comment(comments, new_text)
            if found:
                if comm_writer_id == me:
                    target_card.update_comment(comment_id = com['id'], comment_text=data['action']['text'])
                else:
                    target_card.update_comment(comment_id = com['id'], comment_text="{}:: {}".format(comm_writer.full_name, data['action']['text']))


    return

class Webhook(BaseModel):
    action : dict
    model : dict

@app.post("/mirrorsync", status_code=200, tags=["Endpoints"])
async def sync_cards (
    webhook : Webhook
    ):

    data = webhook.action['data']
    type = webhook.action['type']
    card_id = data['card']['id']

    if lookup.get(card_id) :
        alt_card_id = lookup.get(card_id)['alt_card_id']
        ms_config = lookup.get(alt_card_id)['config']
    else:
        return JSONResponse(content={'result' : 'Skip this trigger.'})


    if 'primary' in lookup.get(card_id).keys():
        ms_primary = lookup.get(card_id)['primary']
        
    else:
        ms_primary = False

    
    (client, me) = trello_client()

    if next ((action for action in ['addLabelToCard', 'removeLabelFromCard'] if action == type), None) and ms_config['MS_LABELS'] == "YES":
        await labels(client, data, card_id, alt_card_id, type)

    elif next ((action for action in ['addChecklistToCard', 'removeChecklistFromCard', 'createCheckItem', 'deleteCheckItem', 'updateCheckItemStateOnCard', 'updateChecklist', 'updateCheckItem', 'updateCheckItemDue', 'updateMemberOnCheckItem'] if action == type), None) and ms_config['MS_CHECKLISTS'] == "YES":
        await checklists (client, data, card_id, alt_card_id, type)

    elif next((action for action in ['updateCustomFieldItem'] if action ==type), None) and ms_config['MS_CUSTOMFIELDS'] == "YES":
        await customfields (client, data, card_id, alt_card_id, type)

    elif next((action for action in ['deleteAttachmentFromCard', 'addAttachmentToCard'] if action == type), None) and ms_config['MS_ATTACHMENTS'] == "YES":
        await attachments (client, data, card_id, alt_card_id, type)
    # Temporary removed
    #elif next((action for action in ['commentCard', 'updateComment'] if action == type), None) and ms_config['MS_COMMENTS'] == "YES":
        #print(data)
        #await comments (client, data, card_id, alt_card_id, type, me, webhook.action['idMemberCreator'], ms_primary )

    elif next((action for action in ['updateCard'] if action == type), None):

        if 'old' in data.keys() :
            if ('due' in data['old'].keys() or 'dueComplete' in data['old'].keys() or 'start' in data['old'].keys() or 'dueReminder' in data['old'].keys()) and ms_config['MS_STARTDUE'] == "YES":
                await dates (client, data, card_id, alt_card_id, type)
            elif 'name' in data['old'].keys() and ms_config['MS_CARDNAME'] == "YES":
                await name (client, data, card_id, alt_card_id, type)
            elif 'desc' in data['old'].keys() and ms_config['MS_CARDDESCRIPTION'] == "YES" :
                await desc (client, data, card_id, alt_card_id, type)
            elif ('address' in data['old'].keys() or 'locationName' in data['old'].keys()) and ms_config['MS_ADDRESS'] == "YES":
                await location (client, data, card_id, alt_card_id, type)
    else:
        return JSONResponse(content={'result' : 'Skip this trigger.'})


    return JSONResponse(content={'result' : 'OK'})

@app.head("/mirrorsync", status_code=200, tags=["Endpoints"])
async def used_by_setup (
    ):

    return JSONResponse(content={'result' : 'OK'})


class Clone(BaseModel):
    card_id : str

@app.post("/clone", status_code=200, tags=["Endpoints"])
async def create_card (
    payload : Clone,
    ):
    card_id = payload.card_id

    if lookup.get(card_id) != None:
        
        return JSONResponse(content={'result' : 'card already has 1-1 sync'}, status_code = status.HTTP_400_BAD_REQUEST)

    (client, me) = trello_client()
    card =  client.get_card (card_id)
    col = card.trello_list

    new_card = col.add_card(name=card.name, source=card_id, keep_from_source="all")

    for cl_s in card.checklists:
        for cl_p in new_card.checklists:
            if cl_s.name == cl_p.name:
                cl_p.delete()
                states = []
                names = []
                advance = {}
                for itm in cl_s.items:

                    if itm['due'] != None or itm['idMember'] != None :
                        advance[itm['name']] = {'due' : itm['due'], 'idMember' : itm['idMember']}
                    names.append(itm['name'])
                    states.append(itm['checked'])
                new_cls = new_card.add_checklist(title=cl_s.name, items=names, itemstates=states)
                if len(advance.keys()) != 0:
                    for itx in new_cls.items:
                        if itx['name'] in advance.keys():
                            if advance[itx['name']]['idMember'] != None :
                                for mbr in client.get_board(new_card.board_id).get_members():
                                    if mbr.id == advance[itx['name']]['idMember']:
                                        new_cls.set_checklist_item_member(itx, mbr)
                            if advance[itx['name']]['due'] != None :
                                due = parse(advance[itx['name']]['due'])
                                new_cls.set_checklist_item_due(itx, due)

    lookup.put({"alt_card_id" : new_card.id, "key" : card_id , "primary" : True, "config" : MS_CONFIG} )
    lookup.put({"alt_card_id" : card_id, "key" : new_card.id , "primary" : False, "config" : MS_CONFIG } )
    create_webhook(card_id, new_card.id)
    
    return JSONResponse(content={"card_id" : card_id, "alt_card_id" : new_card.id})

class Setup(BaseModel):
    card_id : str
    alt_card_id : str

@app.post("/setup", status_code=200, tags=["Endpoints"])
async def create_webhooks (
    payload : Setup
    ):
    card_id = payload.card_id
    alt_card_id = payload.alt_card_id

    if lookup.get(card_id):
        pass
    else:
        lookup.put({"alt_card_id" : alt_card_id, "key" : card_id, "primary" : True, "config" : MS_CONFIG} )
    
    if lookup.get(alt_card_id):
        pass
    else:
        lookup.put({"alt_card_id" : card_id,  "key" : alt_card_id, "primary" : False, "config" : MS_CONFIG} )

    create_webhook(card_id, alt_card_id)

    return JSONResponse(content={'result' : 'OK'})

class Stop(BaseModel):
    card_id : str

@app.post("/stop", status_code=200, tags=["Endpoints"])
async def remove_sync (
    payload : Stop
    ):
    card_id = payload.card_id
    alt_card_id = lookup.get(card_id)['alt_card_id']

    (client, me) = trello_client()
    for hook in client.list_hooks(token=TRELLO_TOKEN):
        if f"https://{INSTANCE_HOSTNAME}" in hook.callback_url and (hook.id_model == card_id or hook.id_model == alt_card_id):
            lookup.delete(hook.id_model)
            hook.delete()
            
    

    return JSONResponse(content={'result' : 'The entries for {} and {} are deleted'.format(card_id, alt_card_id)})


@app.post("/purge", status_code=200, tags=["Endpoints"])
async def purge_all_for_hostname (
    ):

    (client, me) = trello_client()
    for hook in client.list_hooks(token=TRELLO_TOKEN):
        if f"https://{INSTANCE_HOSTNAME}" in hook.callback_url :
            
            hook.delete()
            print(f"{hook.callback_url} is deleted")


    return JSONResponse(content={'result' : 'OK'})
