# -*- coding: utf-8 -*-
"""
GlobaLeaks - The Open-Source Whistleblowing Software
"""
import operator

__author__ = 'GlobaLeaks'
__email__ = 'info@globaleaks.org'
__copyright__ = '2011-2020 - Hermes Center for Transparency and Digital Human Rights - GlobaLeaks Project'
__version__ = '4.0.58'
__license__ = 'AGPL-3.0'

DATABASE_VERSION = 53
FIRST_DATABASE_VERSION_SUPPORTED = 34

# Add new languages as they are supported here! To do this retrieve the name of
# the language and its code from transifex. Then use the following command to
# generate the 'native' unicode string:
#
# python -c "code='ar'; import babel; print('native: %s' % repr(babel.Locale.parse(code).get_display_name(code)));"
#
# NOTE that the cmd requires Babel is installed via pip and `code` is defined.
LANGUAGES_SUPPORTED = [
    {'code': 'ar', 'name': 'Arabic', 'native': '\u0627\u0644\u0639\u0631\u0628\u064a\u0629'},
    {'code': 'az', 'name': 'Azerbaijani', 'native': 'Az\u0259rbaycanca'},
    {'code': 'bg', 'name': 'Bulgarian', 'native': '\u0431\u044a\u043b\u0433\u0430\u0440\u0441\u043a\u0438'},
    {'code': 'bs', 'name': 'Bosnian', 'native': 'Bosanski'},
    {'code': 'ca', 'name': 'Catalan', 'native': 'Catal\xe0'},
    {'code': 'ca@valencia', 'name': 'Valencian', 'native': 'Valenci\xe0'},
    {'code': 'cs', 'name': 'Czech', 'native': '\u010ce\u0161tina'},
    {'code': 'da', 'name': 'Danish', 'native': 'Dansk'},
    {'code': 'de', 'name': 'German', 'native': 'Deutsch'},
    {'code': 'dv', 'name': 'Divehi', 'native': '\u078b\u07a8\u0788\u07ac\u0780\u07a8'},
    {'code': 'el', 'name': 'Greek', 'native': '\u0395\u03bb\u03bb\u03b7\u03bd\u03b9\u03ba\u03ac'},
    {'code': 'en', 'name': 'English', 'native': 'English'},
    {'code': 'es', 'name': 'Spanish', 'native': 'Espa\xf1ol'},
    {'code': 'fa', 'name': 'Persian', 'native': '\u0641\u0627\u0631\u0633\u06cc'},
    {'code': 'fi', 'name': 'Finnish', 'native': 'Suomi'},
    {'code': 'fr', 'name': 'French', 'native': 'Fran\xe7ais'},
    {'code': 'gl', 'name': 'Galician', 'native': 'Galego'},
    {'code': 'he', 'name': 'Hebrew', 'native': '\u05e2\u05d1\u05e8\u05d9\u05ea'},
    {'code': 'hr_HR', 'name': 'Croatian', 'native': 'Hrvatski'},
    {'code': 'hu_HU', 'name': 'Hungarian', 'native': 'Magyar'},
    {'code': 'id', 'name': 'Indonesian', 'native': 'Indonesia'},
    {'code': 'it', 'name': 'Italian', 'native': 'Italiano'},
    {'code': 'ja', 'name': 'Japanese', 'native': '\u65e5\u672c\u8a9e'},
    {'code': 'ka', 'name': 'Georgian', 'native': '\u10e5\u10d0\u10e0\u10d7\u10e3\u10da\u10d8'},
    {'code': 'ko', 'name': 'Korean', 'native': '\ud55c\uad6d\uc5b4'},
    {'code': 'lt', 'name': 'Korean', 'native': 'Llietuvių'},
    {'code': 'mg', 'name': 'Malagasy', 'native': 'Malagasy'},
    {'code': 'nb_NO', 'name': 'Norwegian', 'native': 'Norsk bokm\xe5l'},
    {'code': 'nl', 'name': 'Dutch', 'native': 'Nederlands'},
    {'code': 'pl', 'name': 'Polish', 'native': 'Polski'},
    {'code': 'pt_BR', 'name': 'Portuguese (Brazil)', 'native': 'Portugu\xeas (Brasil)'},
    {'code': 'pt_PT', 'name': 'Portuguese (Portugal)', 'native': 'Portugu\xeas (Portugal)'},
    {'code': 'ro', 'name': 'Romanian', 'native': 'Rom\xe2n\u0103'},
    {'code': 'ru', 'name': 'Russian', 'native': '\u0420\u0443\u0441\u0441\u043a\u0438\u0439'},
    {'code': 'sk', 'name': 'Slovak', 'native': 'Sloven\u010dina'},
    {'code': 'sl_SI', 'name': 'Slovenian', 'native': 'Sloven\u0161\u010dina'},
    {'code': 'sq', 'name': 'Albanian', 'native': 'Shqip'},
    {'code': 'sv', 'name': 'Swedish', 'native': 'Svenska'},
    {'code': 'ta', 'name': 'Tamil', 'native': '\u0ba4\u0bae\u0bbf\u0bb4\u0bcd'},
    {'code': 'th', 'name': 'Thai', 'native': '\u0e44\u0e17\u0e22'},
    {'code': 'tr', 'name': 'Turkish', 'native': 'T\xfcrk\xe7e'},
    {'code': 'uk', 'name': 'Ukrainian', 'native': '\u0423\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u0430'},
    {'code': 'ur', 'name': 'Urdu', 'native': '\u0627\u0631\u062f\u0648'},
    {'code': 'vi', 'name': 'Vietnamese', 'native': 'Ti\u1ebfng Vi\u1ec7t'},
    {'code': 'zh_CN', 'name': 'Chinese (China)', 'native': '\u4e2d\u6587 (\u7b80\u4f53, \u4e2d\u56fd)'},
    {'code': 'zh_TW', 'name': 'Chinese (Taiwan)', 'native': '\u4e2d\u6587 (\u7e41\u9ad4, \u53f0\u7063)'}
]

# Sorting the list of dict using the key 'code'
LANGUAGES_SUPPORTED.sort(key=operator.itemgetter('name'))

# Creating LANGUAGES_SUPPORTED_CODES form the ordered LANGUAGES_SUPPORTED
LANGUAGES_SUPPORTED_CODES = {i['code'] for i in LANGUAGES_SUPPORTED}

# Versioning for exported questionnaire's
QUESTIONNAIRE_EXPORT_VERSION = '0.0.1'
