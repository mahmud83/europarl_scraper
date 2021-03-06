# -*- coding: utf-8 -*-
from scrapy.spiders import Spider
from europarl_scraper.items import EuroparlDebate
import re
import requests
import pandas as pd
import os

DATA_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'data'))

def clean_start_urls():
    df = pd.read_csv(os.path.join(DATA_DIR, 'speech_urls.csv'))
    start_urls = map(lambda x: x.split('&amp')[0], df.url.values)
    yield from set(start_urls)


class EuroParlDebateSpider(Spider):
    """ crawl spider for european parliament debates """
    name = "europarl_debates"
    allowed_domains = ["europarl.europa.eu"]
    start_urls = clean_start_urls()
    response = None

    def remove_returns(self, my_string):
        """ remove returns from strings """
        return my_string.replace('\n', '').replace(
            '\t', '').replace('\r', '').strip()

    def grab_xpath(self, xpath_str, pick_one=False, digit=False,
                   return_str=False):
        """ Some intelligence around how to grab from an xpath. """
        item = self.response.xpath(xpath_str).extract()
        if isinstance(item, list):
            item = [self.remove_returns(i) for i in item
                    if self.remove_returns(i)]
            if len(item) == 1 or pick_one:
                item = item[0]
        if isinstance(item, str):
            item = self.remove_returns(item)
            if item.isdigit() and digit:
                item = float(item)
        if return_str and item == []:
            return ''
        return item

    def parse(self, response):
        """ parse a debate page and extract items """
        items = []
        self.response = response
        counter = 1
        topic = ''.join(
            self.grab_xpath('//td[@class="doc_title"]/text()|' +
                            '//td[@class="doc_title"]/a/text()')[2:])
        topic_links = self.grab_xpath('//td[@class="doc_title"]/a/@href')
        speech_type = self.grab_xpath('//td[@class="title_TA"]/text()')
        date_and_location = self.grab_xpath(
            '//td[@class="doc_title"]/text()')[0]
        speech_date = date_and_location.split('-')[0]
        speech_location = date_and_location.split('-')[1]
        item = None

        for table in response.xpath('//table[tr/td/table]'):
            item = EuroparlDebate()
            item['text_url'] = response.url
            item['speech_location'] = speech_location
            item['speech_date'] = speech_date
            item['speech_type'] = speech_type
            item['topic_links'] = topic_links
            item['topic'] = topic
            item['order'] = counter
            speaker_photo = table.xpath(
                'tr/td/table/tr/td/img[@alt="MPphoto"]/@src').extract()
            if not speaker_photo or re.search(r'[\d]+', speaker_photo[0]) is None:
                item['speaker_id'] = 'n/a'
            else:
                item['speaker_id'] = re.search(r'[\d]+', speaker_photo[0]).group()
            try:
                speaker_info = table.xpath(
                    'tr/td/p/span[@class="doc_subtitle_level1_bis"]/text()'
                ).extract()[0]
                item['speaker_name'] = speaker_info.split('(')[0].strip()
            except IndexError:
                # these are usually procedural notes
                continue
            try:
                item['pol_group'] = re.search(
                    r'\(\w+\)', speaker_info).group().lstrip('(').rstrip(')')
            except AttributeError:
                item['pol_group'] = 'n/a'

            try:
                item['note'] = table.xpath(
                    'tr/td/p[@class="contents"]/span[@class="italic"]/text()'
                ).extract()[0]
            except IndexError:
                item['note'] = ''
            if item['pol_group'] == 'n/a' and re.search('[A-Z]+', item['note']):
                # sometimes the party is instead in the note
                item['pol_group'] = re.search('[A-Z]+', item['note']).group()
            item['text'] = self.remove_returns(' '.join(
                table.xpath('tr/td/p[@class="contents"]/text()').extract()))
            items.append(item)
            counter += 1

        return items
