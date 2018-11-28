#
#
# main() will be run when you invoke this action
#
# @param Cloud Functions actions accept a single parameter, which must be a JSON object.
#
# @return The output of this action, which must be a JSON object.
#
#
from datetime import datetime
import sys
import requests
import pystache
import config

def callAPI(url,method,auth,payload):

    r = None

    if method == 'get':
        r = requests.get(url, auth=auth)
    elif method == 'post':
        r = requests.post(url, auth=auth, json=payload)
    elif method == 'put':
        r = requests.put(url, auth=auth, json=payload)

    try:
        return r.json()
    except:
        return {}


def contentful(method,resource,data):

    endpoint = 'https://cdn.contentful.com'
    auth = None

    url = '{}/spaces/{}/{}?access_token={}'.format(endpoint,config.CONTENTFUL_SPACE_ID,resource,config.CONTENTFUL_ACCESS_TOKEN)
    return callAPI(url,method,auth,data)


def mailchimp(method,resource,data):

    endpoint = 'https://us14.api.mailchimp.com/3.0/'

    url = '{}{}'.format(endpoint,resource)
    return callAPI(url,method,auth=(config.MAILCHIMP_USER,config.MAILCHIMP_API_KEY),payload=data)


def getLinked(type,id):

    # which content type are we getting?
    if (type == 'Asset'):
        content_type = 'assets'
    else:
        content_type = 'entries'

    resource = '{}/{}'.format(content_type,id)
    linked = contentful('get',resource,data=None)

    if content_type == 'assets':
        linked['fields']['file']['url'] = 'https:{}'.format(linked['fields']['file']['url'])

    try:
        return linked['fields']
    except:
        return None


def getContent(params):

    linked_asset = getLinked('Asset',params['article']['featureImage']['sys']['id'])
    params['article']['featureImage'] = linked_asset

    return {
        'article' : params['article']
    }


def getTemplate(template_id):
    resource = 'templates/{}/default-content'.format(template_id)
    default_content = mailchimp('get',resource,data=None)

    if default_content is not None and 'mustache' in default_content['sections']:
        return default_content['sections']['mustache']
    else:
        return None


def createCampaign(content,params):

    response = {}

    # create campaign data
    request = {
        'type' : 'regular',
        'recipients' : {
            'list_id' : config.CAMPAIGN_LIST_ID
        },
        'settings' : {
            'template_id' : config.CAMPAIGN_TEMPLATE_ID,
            'folder_id' : config.CAMPAIGN_FOLDER_ID,
            'title' : 'Latest article : {}'.format(content['article']['title']),
            'from_name' : 'Test',
            'reply_to' : config.CAMPAIGN_REPLY_TO,
            'subject_line' : content['article']['title'],
            'preview_text' : content['article']['lead']
        }
    }

    tid = request['settings']['template_id']

    content['settings'] = request['settings']

    # get the template from MailChimp
    template = getTemplate(tid)

    if template is None:
        return {'message' : 'Could not find the template'}

    # create the HTML
    HTML = pystache.render(template,content)

    # create the campaign
    campaign = mailchimp('post','campaigns',request)

    if campaign is None:
        return {'message' : 'Could not create a campaign'}

    # update the campaign content
    mailchimp('put','campaigns/{}/content'.format(campaign['id']),data={
        'template' : {
            'id' : tid,
            'sections' : {
                'mustache' : HTML
            }
        }
    })

    # send a test
    resource = 'campaigns/{}/actions/test'.format(campaign['id'])
    response['test'] = mailchimp('post',resource,data={
        'test_emails': config.CAMPAIGN_TEST_EMAILS,
        'send_type':'html'
    })

    return response


def main(params):

    content = getContent(params)

    if content is None:
        return {'message':'Nothing to process'}
    else:
        return createCampaign(content,params)


if __name__ == '__main__':
    print(main(config.TEST_PARAMS))
