import datetime
import random
import os
import re
import json
import unicodedata
import logging

import dateutil.parser
from bs4 import BeautifulSoup
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s: %(message)s")

tz_str = '''-12 Y
-11 X NUT SST
-10 W CKT HAST HST TAHT TKT
-9 V AKST GAMT GIT HADT HNY
-8 U AKDT CIST HAY HNP PST PT
-7 T HAP HNR MST PDT
-6 S CST EAST GALT HAR HNC MDT
-5 R CDT COT EASST ECT EST ET HAC HNE PET
-4 Q AST BOT CLT COST EDT FKT GYT HAE HNA PYT
-3 P ADT ART BRT CLST FKST GFT HAA PMST PYST SRT UYT WGT
-2 O BRST FNT PMDT UYST WGST
-1 N AZOT CVT EGT
0 Z EGST GMT UTC WET WT
1 A CET DFT WAT WEDT WEST
2 B CAT CEDT CEST EET SAST WAST
3 C EAT EEDT EEST IDT MSK
4 D AMT AZT GET GST KUYT MSD MUT RET SAMT SCT
5 E AMST AQTT AZST HMT MAWT MVT PKT TFT TJT TMT UZT YEKT
6 F ALMT BIOT BTT IOT KGT NOVT OMST YEKST
7 G CXT DAVT HOVT ICT KRAT NOVST OMSST THA WIB
8 H ACT AWST BDT BNT CAST HKT IRKT KRAST MYT PHT SGT ULAT WITA WST
9 I AWDT IRKST JST KST PWT TLT WDT WIT YAKT
10 K AEST ChST PGT VLAT YAKST YAPT
11 L AEDT LHDT MAGT NCT PONT SBT VLAST VUT
12 M ANAST ANAT FJT GILT MAGST MHT NZST PETST PETT TVT WFT
13 FJST NZDT
11.5 NFT
10.5 ACDT LHST
9.5 ACST
6.5 CCT MMT
5.75 NPT
5.5 SLT
4.5 AFT IRDT
3.5 IRST
-2.5 HAT NDT
-3.5 HNT NST NT
-4.5 HLV VET
-9.5 MART MIT'''

tzd = {}
for tz_descr in map(str.split, tz_str.split('\n')):
    tz_offset = int(float(tz_descr[0]) * 3600)
    for tz_code in tz_descr[1:]:
        tzd[tz_code] = tz_offset


class ReutersPaginator(object):
    def __init__(self, start_date: datetime.date, end_date: datetime.date):
        self.base_url = 'http://www.reuters.com/resources/archive/us/%s.html'
        self.start_date = start_date
        self.end_date = end_date

    @staticmethod
    def _get_article(url, title, date, time, regex: re._pattern_type):
        if '/video/' in url:
            return

        slug_title = ReutersPaginator.slug(title)
        dir = 'articles/%s' % (date)
        if not os.path.exists(dir):
            os.makedirs(dir)
        path = 'articles/%s/%s' % (date, slug_title)
        if os.path.isfile(path):
            return
        r = requests.get(url)
        if r.ok:
            soup = BeautifulSoup(r.content, 'lxml')
            divs = filter(lambda x: x.get('class'), soup.find_all('div'))
            divs = list(filter(lambda x: x['class'][0].startswith('ArticleBody_container_'), divs))

            assert len(divs) == 1

            text = ' '.join([p.text.strip() for p in divs[0].find_all('p')])

            if regex.search(text) is not None:
                with open(path, 'w') as f:
                    json.dump(
                        {
                            'text': text,
                            'time': time,
                            'date': date,
                            'title': title
                        },
                        f,
                    )
                    logging.info('%s - %s', title, date)

    @staticmethod
    def slug(text):
        value = unicodedata.normalize('NFKC', text)
        value = re.sub('[^\w\s-]', '', value, flags=re.U).strip().lower()
        return re.sub('[-\s]+', '-', value, flags=re.U)

    def _get_dates(self):
        current_date = self.start_date
        while current_date < self.end_date:
            yield current_date
            current_date += datetime.timedelta(days=1)

    def _get_matching_title(self, url: str, regex: re._pattern_type, re_ignore: re._pattern_type, date: datetime.date):
        r = requests.get(url)
        links = []
        titles = set()
        if r.ok:
            soup = BeautifulSoup(r.content, 'lxml')
            title_divs = soup.find_all('div', attrs={'class': 'headlineMed'})
            for div in title_divs:
                text = div.text
                if regex.search(text) and re_ignore.search(text) is None:
                    if div.a.text not in titles:
                        print(div.a.text, date)
                        time_str = text.replace(div.a.text, '')
                        time = dateutil.parser.parse(time_str, tzinfos=tzd).timetz().isoformat()
                        links.append(
                            {
                                'url': div.a['href'],
                                'time': time,
                                'title': div.a.text,
                                'date': date.isoformat()
                             }
                        )
                        titles.add(div.a.text)
        return links

    def get_title_urls(self, regex: re._pattern_type, re_ignore: re._pattern_type):
        matched_links = []
        for date in self._get_dates():
            date_str = date.strftime("%Y%m%d")
            url = self.base_url % date_str
            matched_links += self._get_matching_title(url, regex, re_ignore, date)

            with open('matched_titles.json', 'w') as f:
                json.dump(matched_links, f, indent=4)

    def get_articles(self, regex: re._pattern_type):
        with open('matched_titles.json', 'r') as f:
            titles = json.load(f)
        random.shuffle(titles)
        for title in titles:
            self._get_article(title['url'], title['title'], title['date'], title['time'], regex)


def main():

    rr = ReutersPaginator(datetime.date(2007, 1, 1), datetime.date.today())
    # rr.get_title_urls(re.compile(r'\bfed\b|\bfederal\sreserve\b', flags=re.I), re.compile(r'^update\s', re.I))
    rr.get_articles(regex=re.compile(r'\bfederal\sreserve\b', re.I))


if __name__ == "__main__":
    main()