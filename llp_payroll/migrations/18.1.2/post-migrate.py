# -*- coding: utf-8 -*-
"""ADD15 кодтой цалингийн дүрмийг бүх компанид POP1 болгож, бусад дүрмийн
python_code доторх ADD15 лавлагааг POP1-ээр солино.

Бодогдсон утгууд (llp.payroll.rule.value) дүрмийн ID-гаар холбогддог тул
өмнөх цалин бодолтын дүн өөрчлөгдөхгүй. Скриптийг дахин ажиллуулахад аюулгүй:
POP1 аль хэдийн байгаа компанийн ADD15-ийг хөндөхгүй."""

import logging
import re

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

OLD_CODE = 'ADD15'
NEW_CODE = 'POP1'
# Зөвхөн бүтэн үгийг солино (ADD150, XADD15 зэргийг хөндөхгүй).
OLD_CODE_RE = re.compile(r'\b%s\b' % OLD_CODE)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['llp.payroll.rule'].with_context(active_test=False)

    # 1. Дүрмийн кодыг солих (компани тус бүрээр)
    renamed_company_ids = set()
    for rule in Rule.search([('code', '=', OLD_CODE)]):
        if Rule.search_count([('code', '=', NEW_CODE), ('company_id', '=', rule.company_id.id)]):
            _logger.warning(
                'llp.payroll.rule %s (%s): компанид %s код аль хэдийн байгаа тул %s-г солиогүй.',
                rule.id, rule.company_id.display_name, NEW_CODE, OLD_CODE)
            continue
        rule.code = NEW_CODE
        renamed_company_ids.add(rule.company_id.id)
        _logger.info('llp.payroll.rule %s (%s): code %s -> %s',
                     rule.id, rule.company_id.display_name, OLD_CODE, NEW_CODE)

    # 2. Томъёо (python_code) доторх лавлагааг солих — зөвхөн код нь
    #    солигдсон компаниудад (эс тэгвээс өөр POP1 дүрэм рүү заачихна).
    if not renamed_company_ids:
        return
    for rule in Rule.search([('python_code', 'like', OLD_CODE),
                             ('company_id', 'in', list(renamed_company_ids))]):
        new_code = OLD_CODE_RE.sub(NEW_CODE, rule.python_code)
        if new_code != rule.python_code:
            rule.python_code = new_code
            _logger.info('llp.payroll.rule %s [%s] (%s): python_code дотор %s -> %s',
                         rule.id, rule.code, rule.company_id.display_name, OLD_CODE, NEW_CODE)
