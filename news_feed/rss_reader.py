"""
Simple Rss reading module. Provides reading rss
by url. Cashing it into given directory. And reading
from file by date.

You can use it like script with argparse.
Print
>> python rss_reader.py --help
into command line to find more information

"""

import requests
import os

import datetime
from dateutil.parser import parse

import lxml.html as html
import lxml.etree as etree
import xml.etree.ElementTree as ET

import json
import csv
import pandas as pd
import sqlite3

import argparse
import logging

from format_converter import PdfNewsConverter, HTMLNewsConverter


PROJECT_VERSION = '1.0'
PROJECT_DESCRIPTION = ''


class NewsNotFoundError(FileNotFoundError):
    pass


class NewsReader:
    """
        Class for reading news from rss-format files.

        :param: url
    """

    def __init__(self, url, limit=None, caching=False):
        """

        :param url: url of rss
        :param limit: limit of news in feed
        """

        self.url = url
        self.limit = limit
        self.cashing = caching

        self.items = self.get_news()

    def get_news(self):
        """
        Read rss from self.url and creates from it
        dictionary. If self.cashing is True -> cashed news

        :return: dictionary of news
        """

        try:
            request = requests.get(self.url)
        except requests.exceptions.MissingSchema:
            logging.warning(f'Invalid URL: {self.url}. Paste items by yourself.')
            return None

        if not request.ok:
            raise requests.exceptions.InvalidURL(f'You URL is invalid. Status code: {request.status_code}')
        else:
            logging.info('URL is valid, news were collected')

        logging.info(f'Status code: {request.status_code}')  # TODO: create understandable error status output

        result = request.text
        tree = ET.fromstring(result)

        items = dict()
        items.setdefault('title', ' ')
        useful_tags = ['title', 'pubDate', 'link', 'description']

        for head_el in tree[0]:
            if head_el.tag == 'title':
                items['title'] = head_el.text

        for num, item in enumerate(tree.iter('item')):

            if self.limit is not None and self.limit == num:
                break

            items.setdefault(num, {})

            news_description = dict()

            news_description.setdefault('title', 'no title')
            news_description.setdefault('pubDate', str(datetime.datetime.today().date()))
            news_description.setdefault('link', 'no link')
            news_description.setdefault('description', 'no description')

            for description in item:
                if description.tag in useful_tags:
                    news_description[description.tag] = description.text

            text, image_link, image_text = NewsReader.parse_description(news_description['description'])

            news_description['description'] = text
            news_description['imageLink'] = image_link
            news_description['imageDescription'] = image_text

            items[num].update(news_description)

            if self.cashing:
                conn = sqlite3.connect('database.sqlite')
                NewsReader._cash_news_sql(items[num], conn)
                conn.close()

        logging.info('Dictionary from rss-feed was created')

        return items

    @staticmethod
    def _cash_news(news, dir='news_cash'):
        """
        Cashes news into csv format by publication date
        into given directory

        :param news: dictionary of given news
        :param dir: directory into which we save news
        :return: None
        """

        date = NewsReader.get_date(news['pubDate'])
        date = ''.join(str(date).split('-'))

        values = list(news.values())
        column_names = list(news.keys())

        data_temp = pd.DataFrame(data=[values], columns=column_names)

        if not os.path.exists(dir):
            os.mkdir(dir)

        path = os.path.join(dir, date + '.csv')

        if os.path.isfile(path):  # If file exists -> load it into dataframe
            data = pd.read_csv(path)
        else:
            data = pd.DataFrame(columns=column_names)

        is_unique = data_temp.isin(data['title']).sum().sum()

        if not is_unique:
            data = data.append(data_temp)
            data.to_csv(path, index=False)

    @staticmethod
    def _cash_news_sql(news, connection, dir='news_cash'):
        """
        Cashes news into sql database format by publication date
        into given directory

        !Important: connection to database was added for memory saving

        :param news: dictionary of given news
        :param connection: connection to sql database
        :param dir: directory into which we save news
        :return: None
        """

        date = NewsReader.get_date(news['pubDate'])
        date_id = ''.join(str(date).split('-'))

        values = list(news.values())
        column_names = list(news.keys())

        cursor = connection.cursor()

        # TODO: do something with unique values, because UNIQUE isn't really cool

        cursor.execute("""  
            CREATE TABLE IF NOT EXISTS news(
                dateId int NOT NULL,
                pubDate varchar(255),
                title varchar(255) UNIQUE,
                link varchar(255),
                description varchar(1000),
                imageLink varchar(1000),
                imageDescription varchar(1000)
            );
        """)  # is not secure?!

        try:
            cursor.execute("""
                INSERT INTO news
                VALUES (:dateId, :pubDate, :title, :link, :description, :imageLink, :imageDescription)        
            """, {'dateId': date_id,
                  'pubDate': date,
                  'title': news['title'],
                  'link': news['link'],
                  'description': news['description'],
                  'imageLink': news['imageLink'],
                  'imageDescription': news['imageDescription']})
        except sqlite3.IntegrityError:
            pass

        cursor.close()
        connection.commit()

    @staticmethod
    def read_by_date_sql(date, dir='news_cash'):
        """
        Reads news from sql database by given date
        from given directory

        :param date: news date
        :param dir: directory from which we get news
        :return: dictionary of news
        """

        conn = sqlite3.connect('database.sqlite')

        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM news
            WHERE dateId=:date
        """, (date, ))

        data = cursor.fetchall()

        headers = list(map(lambda x: x[0], cursor.description))
        print(headers)

        result = dict()
        for index, row in enumerate(data):
            result.setdefault(index, dict())

            result[index] = dict(zip(headers, row))

        cursor.close()
        conn.close()

        return result

    @staticmethod
    def read_by_date(date, dir='news_cash'):
        """
        Reads news from csv by given date
        from given directory

        :param date: news date
        :param dir: directory from which we get news
        :return: dictionary of news
        """

        dates = os.listdir(dir)

        if date + '.csv' not in dates:
            raise NewsNotFoundError('There is no chased news with such date')

        path = os.path.join(dir, date + '.csv')
        with open(path, 'r', encoding='UTF-8') as file:
            csv_reader = csv.reader(file, delimiter=',',
                                    quotechar='"')

            header = list()
            items = dict()
            for index, row in enumerate(csv_reader):
                if index == 0:
                    header = row
                    continue

                items.setdefault(index, list())

                items[index] = dict(zip(header, row))

        return items

    @staticmethod
    def get_date(news_date):
        """
        Returns date of news publication

        :param news: string date from dictionary of given news
        :return: date of news publication
        """

        try:
            news_date = parse(news_date)
        except ValueError:
            print('There is not date. Today\'s has been pasted')
            news_date = datetime.datetime.today()

        news_date = news_date.date()

        return news_date

    @staticmethod
    def parse_description(description):
        """
        Return news description

        :param description: raw news description
        :return: news description
        """

        text = NewsReader.get_description(description)
        image = NewsReader.get_image(description)

        # TODO: deal with image indexing
        image_link = image[0]
        image_text = image[1]

        return text, image_link, image_text

    @staticmethod
    def get_description(description):
        """
        Remove all tags from raw description and
        return just simple news description

        :param description: news description
        :return: processed description
        """

        try:
            node = html.fromstring(description)
        except etree.ParserError:
            return ''

        return node.text_content()

    @staticmethod
    def get_image(description):
        """
        Parse description file trying to find image
        source and description of this image

        :param description: raw news description
        :return: image source, image description
        """

        xhtml = html.fromstring(description)
        image_src = xhtml.xpath('//img/@src')
        image_description = xhtml.xpath('//img/@alt')

        if len(image_src) == 0:
            image_src = 'No image'
        else:
            image_src = image_src[0]

        if len(image_description) == 0:
            image_description = 'No image description'
        else:
            image_description = image_description[0]

        return image_src, image_description

    @staticmethod
    def news_text(news):
        """
        Process news in dictionary format into
        readable text

        :param news: news dictionary
        :return: readable news description
        """

        result = "\n\tTitle: {}\n\tDate: {}\n\tLink: {}\n\n\tImage link: {}\n\t" \
                 "Image description: {}\n\tDescription: {}".format(news['title'],
                                                                   news['pubDate'],
                                                                   news['link'],
                                                                   news['imageLink'],
                                                                   news['imageDescription'],
                                                                   news['description'])

        return result

    def fancy_output(self, items):
        """
        Output readable information about news
        from items dictionary

        :return: None
        """

        logging.info(print('News feed is ready'))

        for key, value in items.items():
            if key == 'title':
                print(f'Feed: {value}')
            else:
                print(self.news_text(value))

            print('_' * 100)

    @staticmethod
    def to_json(items):
        """
        Convert self.items (all news description)
        into json format

        :return: json format news
        """

        logging.info('Json was created')

        json_result = json.dumps(items)

        return json_result


# feed = NewsReader('https://news.yahoo.com/rss/', limit=10, cashing=True)
# items = feed.read_by_date_sql('20191112')
#
# print(items)
# feed.fancy_output(items)
#
# print(items)


def main():
    parser = argparse.ArgumentParser(description='Pure Python command-line RSS reader')

    parser.add_argument('source', type=str, help='RSS URL')

    parser.add_argument('--version', help='Print version info', action='store_true')
    parser.add_argument('--json', help='Print result as json in stdout', action='store_true')
    parser.add_argument('--verbose', help='Output verbose status messages', action='store_true')
    parser.add_argument('--caching', help='Cache news if chosen', action='store_true')

    # TODO: add flags to output logs
    parser.add_argument('--limit', type=int, help='Limit news topics if this parameter provided')
    parser.add_argument('--date', type=str, help='Reads cashed news by date. And output them')

    parser.add_argument('--to-pdf', type=str,
                        help='Read rss by url and write it into pdf. Print file name as input')
    parser.add_argument('--to-html', type=str,
                        help='Read rss by url and write it into html. Print file name as input')

    args = parser.parse_args()

    if args.version:
        print(PROJECT_VERSION)
        print(PROJECT_DESCRIPTION)

    if args.verbose:
        logging.basicConfig(format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s] %(message)s',
                            level=logging.DEBUG)
    else:
        # logging.basicConfig()
        pass

    if args.json:
        news = NewsReader(args.source, args.limit, args.caching)

        if args.date:
            print(news.to_json(news.read_by_date_sql(args.date)))
        else:
            print(news.to_json(news))

    elif args.date:
        news = NewsReader(args.source, args.limit, args.caching)
        items = news.read_by_date_sql(args.date)

        news.fancy_output(items)
    elif args.to_pdf:
        news = NewsReader(args.source, args.limit, args.caching)
        it = news.items

        pdf = PdfNewsConverter(it)
        pdf.add_all_news()
        pdf.output(args.to_pdf, 'F')
    elif args.to_html:
        news = NewsReader(args.source, args.limit, args.caching)
        it = news.items

        html_converter = HTMLNewsConverter(it)
        html_converter.output(args.to_html)
    else:
        news = NewsReader(args.source, args.limit, args.caching)

        news.fancy_output(news.items)


if __name__ == '__main__':
    main()
