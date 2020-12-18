import requests
import time
from bs4 import BeautifulSoup as soup
import re
import json
import traceback


class Olx(object):
    root = 'https://www.olx.ua/'
    base_ajax = 'https://www.olx.ua/ajax'  # это всё можно найти в <script>, на странице объявления, который добавляет кучу переменных

    log_requests = False
    request_num = 1

    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.183 Safari/537.36'}
        self.history = []

    def check_history(self, link, params):
        try:
            if self.history[-1] == (link + json.dumps(params)):
                return True
            else:
                return False
        except IndexError:
            return False

    def log_request(self, url, params, headers):

        headers_string = json.dumps(headers).replace('{', '').replace('}', '').replace(',', '\r\n')

        # params_string = ""

        params_string = json.dumps(params).replace('{', '').replace('}', '').replace(':', '=').replace(',', '&')

        # for p_name, p_val in params:
        #    params_string += p_name + "=" + p_val + "&"

        file = open('log_' + str(Olx.request_num) + '.txt', 'wb')

        file.write((url + "\r\n" + params_string + "\r\n" + headers_string + "\r\n\r\n" + self.last_response).encode())

        file.close()

    def get_page_by_url(self, url, params={}, headers={}):

        # print ('get_page_by_url call')

        if self.check_history(url, params) != False:
            return self.last_response
        else:
            result = self.session.get(url, params=params, headers=headers)
            self.last_response = result.text

            self.history.append(url + json.dumps(params))

            if Olx.log_requests:
                self.log_request(url, params, headers)

            Olx.request_num += 1

            return self.last_response

    def get_main_page(self):
        return self.get_page_by_url(Olx.root)

    def get_categories(self):

        print('get_categories call.')

        html_tree = soup(self.get_main_page(), "html.parser")

        category_links = html_tree.select('.maincategories-list a')

        self.categories = {}

        for category in category_links:
            category_id = category['data-id']
            category_name = category.select('span')[0].text
            category_url = category['href'].split(Olx.root)[1]

            self.categories[category_name] = {'url': category_url,
                                              'id': category_id,
                                              'child_categories': {}}

            self.categories[category_name]['child_categories'] = self.get_subcategories(category_id)

        # print(self.categories)

    def get_subcategories(self, category_id):

        print('get_subcategories call.')

        html_tree = soup(self.get_main_page(), "html.parser")

        subcategory_links = html_tree.select('.subcategories-list[data-subcategory="' + category_id + '"]')[0].select(
            'a')

        subcategories = {}

        skip_first = True  # первое - "смотреть все объявления", во первых - не нужно, во-вторых - не имеет спанов что вызывает exception'ы
        for subcategory in subcategory_links:

            if skip_first:
                skip_first = False
                continue

            subcategory_name = subcategory.select('span span')[0].text
            subcategory_url = subcategory['href'].split(Olx.root)[1]
            subcategory_id = subcategory['data-id']

            subcategories[subcategory_name] = {'url': subcategory_url,
                                               'id': subcategory_id}

        return subcategories

    def find_category_by_id(self, category_array, search_category_id):  # рекурсивная

        print('find_category_by_id call.')

        for category_name in category_array:

            # print(category_name)

            if category_array[category_name]['id'] == search_category_id:
                return category_array[category_name]

            elif 'child_categories' in category_array[category_name]:
                leveldown = self.find_category_by_id(category_array[category_name]['child_categories'],
                                                     search_category_id)

                if leveldown != False:
                    return leveldown

        return False

    def wrap_query(self, search_words):
        return "q-" + search_words.replace(' ', '-') + "/"

    def get_ads_from_category(self, search_category_id='', category_path='', search_words='', page=1):

        print('get_ads_from_category call.')

        id = True
        path = True

        if category_path == '':
            path = False

        if search_category_id == '':
            id = False

        if id == False and path == False:
            raise Exception('You must pass category id or path to the function!!!')

        if path == False:

            needed_category = {}

            search_result = self.find_category_by_id(self.categories, search_category_id)

            if search_result == False:
                raise Exception('Nonexistent category!!!')
            else:
                needed_category = search_result

            category_path = needed_category['url']

        full_url = Olx.root + category_path + self.wrap_query(search_words)

        print(full_url)

        params = {}
        params['page'] = str(page)

        # for option in search_options...
        # params[option] = ...                               #различные фильтры и параметры поиска, когда-нибудь, ну похуй попозже)))

        result = self.get_page_by_url(full_url, params)

        html_tree = soup(result, "html.parser")

        ads = html_tree.select('#offers_table tr.wrap table')

        # print ('ADS COUNT: ', len(ads))

        ad_array = []

        for ad in ads:

            try:
                ad_url = ad.select('td')[0].select('a')[0]['href'].split(Olx.root)[1]
                ad_pic = ad.select('td')[0].select('a')[0].select('img')[0]['src']
                ad_name = ad.select('td')[1].select('h3 a strong')[0].text

                ad_array.append({'url': ad_url, 'img': ad_pic, 'name': ad_name})

            except Exception as ex:
                print('Исключение: Картинка не найдена!')

        return ad_array

    def get_ad(self, ad_url):

        # print ('get_ad call.')

        result = self.get_page_by_url(ad_url)

        html_tree = soup(result, "html.parser")

        phone_token = ""

        for code in html_tree.select('script'):  # почему-то именно тэг script не имеет атрибута text, я нагуглил атрибут string, но он тоже взвращает пустоту, но при выводе через принт всё норм, поэтому я просто вызываю преобразование в строку, которое офк прописано в классе и достаёт содержимое класса Tag, а именно нашего элемента

            expected_phone_token = re.findall(r"var\s+phoneToken\s*=\s'([0-9a-z]{12,})'", str(code))

            if len(expected_phone_token) > 0:
                phone_token = expected_phone_token[0]
        try:
            ad_title = ''
            ad_description = html_tree.select('#textContent')[0].text
            ad_images = [img['href'] for img in html_tree.select('#descGallery a')]
            ad_phone_token = phone_token

            get_phone_button = html_tree.select('.link-phone')

            phone_exists = False

            if len(get_phone_button) > 0:
                phone_exists = True

                get_phone_button = html_tree.select('.link-phone')[0]

                ad_phone_button_class = ' '.join(get_phone_button['class'])
                ad_phone_button_json = re.findall('\{.*\}', ad_phone_button_class)[0]
                ad_phone_req_details = json.loads(ad_phone_button_json.replace("'", '"'))

            ad_person = {}

            user_block = html_tree.select('.offer-sidebar__box .offer-user__details')[0]
            city_block = html_tree.select('.offer-sidebar__box .offer-user__location')[0]

            ad_person['city'] = city_block.select('.offer-user__address address')[0].text.strip()
            ad_person['name'] = user_block.select('.offer-user__actions h4 a')[0].text.strip()
            ad_person['link'] = user_block.select('.offer-user__actions h4 a')[0]['href']

        except IndexError:
            print('Исключение: не найдены картинки объявления!')
            print(traceback.format_exc())

        ad_info = {'title': ad_title,
                   'description': ad_description,
                   'images': ad_images,
                   'person': ad_person}

        if phone_exists:
            ad_info['phoneToken'] = ad_phone_token
            ad_info['phoneRequestDetails'] = ad_phone_req_details

        return ad_info

    def get_phone_number_from_ad(self, ad, ad_url):

        # var url = www_base_ajax + '/misc/contact/' + path + '/' + id + '/'; JS - код отвечающий за формирование запроса номера телефона
        # функция processShowNumber

        request_details = ad['phoneRequestDetails']

        url = Olx.base_ajax + '/misc/contact/' + request_details['path'] + '/' + request_details['id']

        # print (url)

        return self.get_page_by_url(url, {'pt': ad['phoneToken']}, {'Referer': Olx.root + ad_url})

