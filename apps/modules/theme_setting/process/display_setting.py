# -*-coding:utf-8-*-
import time
from uuid import uuid1
from bson import ObjectId
from flask import request
from flask_babel import gettext
from flask_login import current_user

from apps.app import mdb_web, mdb_sys
from apps.core.flask.reqparse import arg_verify
from apps.core.utils.get_config import get_config
from apps.modules.upload.process.tempfile import clean_tempfile
from apps.modules.upload.process.upload_file import file_upload
from apps.utils.format.obj_format import str_to_num, json_to_pyseq
from apps.utils.paging.paging import datas_paging
from apps.utils.text_parsing.text_parsing import richtext_extract_img
from apps.utils.upload.file_up import file_del
from apps.utils.upload.get_filepath import get_file_url

__author__ = "Allen Woo"

def add_display_setting():

    '''
    :return:
    '''

    user_id = 0
    batch = request.argget.all("batch", False)
    name = request.argget.all("name")
    link = request.argget.all("link")
    link_open_new_tab = str_to_num(request.argget.all("link_open_new_tab",1))
    link_name = request.argget.all("link_name")
    title = request.argget.all("title")
    text = request.argget.all("text","")
    text_html = request.argget.all("text_html", "")
    ctype = request.argget.all("ctype")
    category_id = request.argget.all("category_id")
    data = {}
    category = "Default"

    if category_id and category_id.lower() != "default":
        display_setting_category = mdb_web.db.category.find_one({"_id":ObjectId(category_id)})
        if display_setting_category:
            category = display_setting_category["name"]
    elif not category_id or category_id.lower() == "default":
        category_id = ""

    s, r = arg_verify([(gettext("type"), ctype)],
                      only=get_config("category","CATEGORY_TYPE").values())
    if not s:
        return r
    s, r = arg_verify([(gettext("name"), name)], required=True)
    if not s and not batch:
        return r

    # 如果有上传文件
    if request.files:
        data = file_upload(return_key=True, prefix="multidisplay_setting/{}/".format(ctype))
        if data["msg_type"] != "s":
            return data

    if not batch and mdb_sys.db.theme_display_setting.find_one({"name":name, "type":ctype}):
        type_alias = ctype
        for k,v in get_config("category","CATEGORY_TYPE").items():
            if v == ctype:
                type_alias = k
                break
        data = {"msg":gettext('The type "{}" exists in the name "{}"').format(type_alias, name),
                "msg_type":"w", "http_status":403}
    else:
        # 获取text_html使用的图片
        text_imgs = []
        if text_html:
            srcs = richtext_extract_img(richtext=text_html)
        else:
            srcs = []
        text_imgs = clean_tempfile(user_id=current_user.str_id,
                              type="image",
                              keey_file=srcs)

        info = {
            "category": category,
            "category_id": category_id,
            "link": link,
            "link_open_new_tab":link_open_new_tab,
            "link_name":link_name,
            "title": title,
            "text": text,
            "text_html":text_html,
            "text_imgs":text_imgs,
            "type": ctype,
            "time":time.time(),
            "user_id":user_id
        }
        if "keys" in data:
            for key in data["keys"]:
                rand_name = "{}_{}".format(name ,uuid1())
                info["name"] = rand_name
                info["url"] = key
            mdb_sys.db.theme_display_setting.insert_one(info)
            data["msg"] = gettext("{} uploaded successfully").format(ctype.capitalize())
        else:
            info["name"] = name
            info["url"] = None
            mdb_sys.db.theme_display_setting.insert_one(info)
            data["msg"] = gettext("Added successfully").format(ctype.capitalize())
        data["msg_type"] = "s"
        data["http_status"] = 201

    return data

def get_display_setting():
    '''
    :param user_id: 媒体为管理端(系统)所有时需要传入user_id = 0
    :return:
    '''

    user_id = 0
    id = request.argget.all("id")

    s, r = arg_verify([("id", id)], required=True)
    if not s:
        return r

    data = {}

    display_setting = mdb_sys.db.theme_display_setting.find_one({"_id":ObjectId(id), "user_id":user_id})
    if display_setting:
        display_setting["_id"] = str(display_setting["_id"])
        if "url" in display_setting and display_setting["url"]:
            display_setting["url"] = get_file_url(display_setting["url"])

    data["media"] = display_setting
    return data


def get_display_settings():

    '''
    :return:
    '''

    user_id = 0
    keyword = request.argget.all("keyword")
    category_id = request.argget.all("category_id")
    ctype = request.argget.all("ctype")
    page = str_to_num(request.argget.all("page",1))
    pre = str_to_num(request.argget.all("pre", 12))
    sort = json_to_pyseq(request.argget.all('sort'))
    s, r = arg_verify([(gettext("type"), ctype)],
                      only=get_config("category","CATEGORY_TYPE").values())
    if not s:
        return r

    data = {}
    if category_id:
        if category_id == "default":
            category_id = {"$in":[None, ""]}
        query = {"category_id":category_id, "type":ctype}
    else:
        query = {"type": ctype}

    if keyword:
        k_rule = {"$regex":keyword, "$options":"$i"}
        query["$or"] = [{"name":k_rule}, {"title":k_rule}, {"link":k_rule}, {"text":k_rule}]
    query["user_id"] = user_id

    # sort
    if sort:
        for i in range(0, len(sort)):
            sort[i] = (list(sort[i].keys())[0], list(sort[i].values())[0])
    else:
        sort = [("time", -1)]
    display_settings = mdb_sys.db.theme_display_setting.find(query)
    data_cnt = display_settings.count(True)
    display_settings = list(display_settings.sort(sort).skip(pre * (page - 1)).limit(pre))
    for d in display_settings:
        d["_id"] = str(d["_id"])
        if "url" in d and d["url"]:
            d["url"] = get_file_url(d["url"])

    data["medias"] = datas_paging(pre=pre, page_num=page, data_cnt=data_cnt, datas=display_settings)
    return data

def edit_display_setting():

    '''
    :return:
    '''
    user_id = 0
    display_setting_id = request.argget.all("id")
    name = request.argget.all("name")
    link = request.argget.all("link")
    link_name = request.argget.all("link_name")
    link_open_new_tab = str_to_num(request.argget.all("link_open_new_tab", 1))
    title = request.argget.all("title")
    text = request.argget.all("text","")
    text_html = request.argget.all("text_html", "")
    category_id = request.argget.all("category_id")
    s, r = arg_verify([("id", display_setting_id)], required=True)
    if not s:
        return r

    s, r = arg_verify([(gettext("name"), name)], required=True)
    if not s:
        return r

    old_display_setting = mdb_sys.db.theme_display_setting.find_one({"_id":ObjectId(display_setting_id)})

    # 如果只是更新图片, 则保存上传图片
    if request.files:
        data = file_upload(return_key=True, prefix="multidisplay_setting/{}/".format(old_display_setting["type"]))
        if data["msg_type"] != "s":
            return data
        else:
            # 删除旧的图片
            if "url" in old_display_setting:
                file_del(old_display_setting["url"])
            temp_url = None
            if "keys" in data:
                for key in data["keys"]:
                    temp_url = key
                if temp_url:
                    mdb_sys.db.theme_display_setting.update_one({"_id": ObjectId(display_setting_id), "user_id": user_id},
                                                {"$set": {"url":temp_url}})
                    data = {"msg": gettext("Update picture successfully"), "msg_type": "s", "http_status": 201}
                else:
                    data = {"msg": gettext("Failed to update"), "msg_type": "e", "http_status": 400}
            return data


    category = "Default"
    not_updated_category = False
    if category_id == None:
        # 不更新category
        not_updated_category = True
    elif category_id and category_id.lower() != "default":
        display_setting_category = mdb_web.db.category.find_one({"_id": ObjectId(category_id)})
        if display_setting_category:
            category = display_setting_category["name"]

    elif category_id.lower() == "default":
        category_id = ""

    # 处理其他字段更新
    query = {"name": name, "type":old_display_setting["type"],"_id": {"$ne": ObjectId(display_setting_id)}}
    if mdb_sys.db.theme_display_setting.find_one(query):
        type_alias = old_display_setting["type"]

        for k, v in get_config("category", "CATEGORY_TYPE").items():
            if v == old_display_setting["type"]:
                type_alias = k
                break
        data = {"msg":gettext('The type "{}" exists in the name "{}"').format(type_alias, name),
                "msg_type":"w", "http_status":403}
    else:
        # 获取text_html使用的图片
        old_imgs = old_display_setting.get("text_imgs", [])
        if text_html:
            srcs = richtext_extract_img(richtext=text_html)
        else:
            srcs = []

        text_imgs = clean_tempfile(user_id=current_user.str_id,
                                   type="image",old_file=old_imgs,
                                   keey_file=srcs)
        info = {
            "name":name,
            "link": link,
            "link_name":link_name,
            "link_open_new_tab":link_open_new_tab,
            "title": title,
            "text": text,
            "text_html":text_html,
            "text_imgs":text_imgs
        }

        if not not_updated_category:
            info["category_id"] = category_id
            info["category"] = category

        r = mdb_sys.db.theme_display_setting.update_one({"_id":ObjectId(display_setting_id),"user_id":user_id},
                                    {"$set":info})
        if r.modified_count:
            data = {"msg":gettext("Modify the success"), "msg_type":"s", "http_status":201}
        else:
            data = {"msg": gettext("The content is not modified"), "msg_type": "w", "http_status": 400}

    return data

def del_display_setting():
    '''
    :return:
    '''

    user_id = 0
    display_setting_ids = json_to_pyseq(request.argget.all("ids",[]))
    deleted_count = 0
    for id in display_setting_ids:
        display_setting = mdb_sys.db.theme_display_setting.find_one({"_id": ObjectId(id), "user_id":user_id})
        r = mdb_sys.db.theme_display_setting.delete_one({"_id":ObjectId(id), "user_id":user_id})
        # 是否存在上传的文件
        if r.deleted_count and "url" in display_setting and display_setting["url"]:
            file_del(display_setting["url"])
            deleted_count += 1
        else:
            deleted_count += 1

    if deleted_count:
        data = {"msg":gettext("{} files have been deleted").format(deleted_count), "msg_type":"s", "http_status":204}
    else:
        data = {"msg": gettext("Failed to delete"), "msg_type": "w", "http_status": 400}

    return data