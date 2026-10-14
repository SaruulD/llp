# -*- coding: utf-8 -*-
"""Хавсран ажлын мэдээлэл hr.contract-ийн 4 талбараас part_time_work_ids
жагсаалт руу шилжсэн. Хуучин shortcut template-ээр бичигдсэн дүрмүүдийн
python_code-ийг шинэ template-ээр солино. Гараар өөрчилсөн кодыг хөндөхгүй."""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

OLD_TEMPLATES = {
    'part_time_work_additional_salary': """result = 0
if object:
    if object.part_time_work_start_date or object.part_time_work_end_date:
        if object.part_time_work_start_date >= payroll_start_date and object.part_time_work_start_date <= payroll_end_date or payroll_start_date <= object.part_time_work_end_date and payroll_end_date >= object.part_time_work_end_date or object.part_time_work_start_date <= payroll_start_date and payroll_end_date <= object.part_time_work_end_date:
            result = object.part_time_work_additional_salary""",
    'part_time_work_additional_salary_percent': """result = 0
if object:
    if object.part_time_work_start_date or object.part_time_work_end_date:
        if object.part_time_work_start_date >= payroll_start_date and object.part_time_work_start_date <= payroll_end_date or payroll_start_date <= object.part_time_work_end_date and payroll_end_date >= object.part_time_work_end_date or object.part_time_work_start_date <= payroll_start_date and payroll_end_date <= object.part_time_work_end_date:
            result = object.part_time_work_additional_salary_percent""",
}


def _normalize(code):
    return '\n'.join(line.rstrip() for line in (code or '').strip().splitlines())


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['llp.payroll.rule'].with_context(active_test=False)
    templates = Rule._get_python_code_templates()
    for object_type, old_code in OLD_TEMPLATES.items():
        for rule in Rule.search([('object_type', '=', object_type)]):
            if _normalize(rule.python_code) == _normalize(old_code):
                rule.python_code = templates[object_type]
            elif 'part_time_work_' in (rule.python_code or '') and 'part_time_work_ids' not in rule.python_code:
                _logger.warning(
                    'llp.payroll.rule %s (%s): python_code нь устсан part_time_work_* талбарыг '
                    'ашиглаж байгаа тул гараар part_time_work_ids руу засна уу.', rule.id, rule.code)
    # object_type-гүй ч хуучин талбар ашигласан дүрмүүдийг лог-д үлдээнэ
    for rule in Rule.search([('python_code', 'ilike', 'object.part_time_work_'),
                             ('object_type', 'not in', list(OLD_TEMPLATES))]):
        if 'part_time_work_ids' not in rule.python_code:
            _logger.warning(
                'llp.payroll.rule %s (%s): python_code нь устсан part_time_work_* талбарыг '
                'ашиглаж байгаа тул гараар part_time_work_ids руу засна уу.', rule.id, rule.code)
