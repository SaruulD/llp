# -*- coding: utf-8 -*-

from odoo.tools.translate import _ # type: ignore
from odoo import api, fields, models, _, modules # type: ignore
from datetime import datetime,timedelta
from operator import itemgetter
import xlsxwriter # type: ignore
from io import BytesIO
import base64
import logging
from odoo.exceptions import UserError # type: ignore

_logger = logging.getLogger(__name__)

class LLPPayrollSalaryReport(models.TransientModel):
    _name = 'llp.payroll.salary.report'

    start_date = fields.Date(string="Start date")
    end_date = fields.Date(string="End date")
    department_ids = fields.Many2many('hr.department', string="Departments", tracking=True)
    export_type = fields.Selection([('excel','Excel'),('pdf','PDF')],string="Export type",default="excel")
    struct_id = fields.Many2one('llp.payroll.structure',string="Stucture", domain="[('state','=','done')]",tracking=True)
        
    def _get_report_data(self):
        self.ensure_one()

        # department_id on llp.payroll is a Many2many field, so it has no
        # physical column on llp_payroll - it lives in an auto-generated
        # relation table. Look that table/columns up dynamically instead of
        # referencing A.department_id directly (same pattern used in
        # llp_payroll_employee_vacation.py action_get_data()).
        m2m_field = self.env['llp.payroll']._fields['department_id']
        rel_table = m2m_field.relation
        rel_col1 = m2m_field.column1
        rel_col2 = m2m_field.column2

        query = f"""
            SELECT
                A.id AS payroll_id,
                H.id AS department_id,
                H.complete_name AS department_name,
                B.employee_id AS employee_id,
                G.firstname AS firstname,
                G.lastname AS lastname,

                E.id AS rule_id,
                E.name AS rule_name,
                E.is_show_sum AS is_show_sum,
                E.rulefield_type AS rulefield_type,

                COALESCE(F.value, 0) AS value,
                COALESCE(F.char_value, '') AS char_value,

                D.sequence AS sequence
            FROM llp_payroll A
                LEFT JOIN llp_payroll_line B ON B.payroll_id = A.id
                LEFT JOIN llp_payroll_structure C ON C.id = A.struct_id
                LEFT JOIN llp_payroll_structure_line D ON D.struct_id = C.id
                LEFT JOIN llp_payroll_rule E
                    ON E.id = D.rule_id AND E.show_in_report = true
                LEFT JOIN llp_payroll_rule_value F
                    ON F.payroll_rule_id = E.id AND B.id = F.line_id
                LEFT JOIN hr_employee G ON G.id = B.employee_id
                LEFT JOIN {rel_table} REL ON REL.{rel_col1} = A.id
                LEFT JOIN hr_department H ON H.id = REL.{rel_col2}
            WHERE A.state = 'confirmed'
            AND A.start_date = %s
            AND A.end_date   = %s
            AND C.id         = %s
        """
        params = [self.start_date, self.end_date, self.struct_id.id]

        # Only add department filter when selected
        if self.department_ids:
            query += " AND H.id IN %s"
            params.append(tuple(self.department_ids.ids))

        query += " ORDER BY H.complete_name, G.name, D.sequence"

        self.env.cr.execute(query, tuple(params))
        cols = [d[0] for d in self.env.cr.description]
        rows = [dict(zip(cols, r)) for r in self.env.cr.fetchall()]

        payrolls = {}
        for dic in rows:
            pid = dic['payroll_id']
            payrolls.setdefault(pid, {
                'payroll_id': pid,
                'department_name': dic.get('department_name') or 'Тодорхойгүй',
                'employees': {}
            })

            eid = dic['employee_id']
            payrolls[pid]['employees'].setdefault(eid, {
                'firstname': dic.get('firstname') or 'Тодорхойгүй',
                'lastname': dic.get('lastname') or 'Тодорхойгүй',
                'rules': {}
            })

            rid = dic['rule_id']
            payrolls[pid]['employees'][eid]['rules'][rid] = {
                'name': dic.get('rule_name') or '',
                'value': float(dic.get('value') or 0.0),
                'char_value': dic.get('char_value') or '',
                'rulefield_type': dic.get('rulefield_type') or 'float',
                'sequence': int(dic.get('sequence') or 999999),
                'is_show_sum': bool(dic.get('is_show_sum')),
            }

        # global rule headers once (same as excel)
        rules_map = {}
        for p in payrolls.values():
            for emp in p['employees'].values():
                for rid, r in emp['rules'].items():
                    rules_map[rid] = (r['sequence'], r['name'], r['rulefield_type'], r['is_show_sum'])

        rule_ids = [rid for rid, _ in sorted(rules_map.items(), key=lambda x: (x[1][0], x[1][1]))]

        return {
            'file_name': 'Цалингийн тайлан',
            'payrolls': payrolls,
            'rules_map': rules_map,
            'rule_ids': rule_ids,
        }


    def action_export_pdf(self):
        self.ensure_one()
        # This xmlid must match your ir.actions.report id (see below)
        return self.env.ref('llp_payroll.action_report_payroll_matrix_pdf').report_action(self)


    def action_export(self):
        self.ensure_one()

        # department_id on llp.payroll is a Many2many field - no physical
        # column on llp_payroll, so look up its relation table/columns
        # dynamically rather than referencing A.department_id directly.
        m2m_field = self.env['llp.payroll']._fields['department_id']
        rel_table = m2m_field.relation
        rel_col1 = m2m_field.column1
        rel_col2 = m2m_field.column2

        query = f"""
            SELECT
                A.id AS payroll_id,
                H.id AS department_id,
                H.complete_name AS department_name,

                B.employee_id AS employee_id,
                G.firstname AS firstname,
                G.lastname AS lastname,

                E.id AS rule_id,
                E.name AS rule_name,
                E.code AS rule_code,
                E.is_show_sum AS is_show_sum,
                E.rulefield_type AS rulefield_type,

                COALESCE(F.value, 0) AS value,
                COALESCE(F.char_value, '') AS char_value,

                D.sequence AS sequence
            FROM llp_payroll A
                LEFT JOIN llp_payroll_line B ON B.payroll_id = A.id
                LEFT JOIN llp_payroll_structure C ON C.id = A.struct_id
                LEFT JOIN llp_payroll_structure_line D ON D.struct_id = C.id
                LEFT JOIN llp_payroll_rule E
                    ON E.id = D.rule_id AND E.show_in_report = true
                LEFT JOIN llp_payroll_rule_value F
                    ON F.payroll_rule_id = E.id AND B.id = F.line_id
                LEFT JOIN hr_employee G ON G.id = B.employee_id
                LEFT JOIN {rel_table} REL ON REL.{rel_col1} = A.id
                LEFT JOIN hr_department H ON H.id = REL.{rel_col2}
            WHERE A.state = 'confirmed'
            AND A.start_date = %s
            AND A.end_date   = %s
            AND C.id         = %s
        """
        params = [self.start_date, self.end_date, self.struct_id.id]

        if self.department_ids:
            query += " AND H.id IN %s"
            params.append(tuple(self.department_ids.ids))

        query += " ORDER BY H.complete_name, G.name, D.sequence"

        self.env.cr.execute(query, tuple(params))
        cols = [d[0] for d in self.env.cr.description]
        rows = [dict(zip(cols, r)) for r in self.env.cr.fetchall()]
        if not rows:
            raise UserError("Өгөгдөл олдсонгүй.")

        payrolls = {}
        for dic in rows:
            payroll_id = dic['payroll_id']
            if payroll_id not in payrolls:
                payrolls[payroll_id] = {
                    'payroll_id': payroll_id,
                    'department_id': dic.get('department_id', 0),
                    'department_name': dic.get('department_name') or u'Тодорхойгүй',
                    'employees': {},
                }

            emp_id = dic['employee_id']
            if emp_id not in payrolls[payroll_id]['employees']:
                payrolls[payroll_id]['employees'][emp_id] = {
                    'employee_id': emp_id,
                    'firstname': dic.get('firstname') or u'Тодорхойгүй',
                    'lastname': dic.get('lastname') or u'Тодорхойгүй',
                    'rules': {},
                }

            rule_id = dic['rule_id']
            payrolls[payroll_id]['employees'][emp_id]['rules'][rule_id] = {
                'rule_id': rule_id,
                'name': dic.get('rule_name') or u'Тодорхойгүй',
                'code': dic.get('rule_code') or u'Тодорхойгүй',
                'value': float(dic.get('value') or 0.0),
                'char_value': dic.get('char_value') or '',
                'rulefield_type': dic.get('rulefield_type') or 'float',
                'sequence': int(dic.get('sequence') or 999999),
                'is_show_sum': bool(dic.get('is_show_sum')),
            }

        rules_map = {}
        for p in payrolls.values():
            for emp in p['employees'].values():
                for rid, rule in emp['rules'].items():
                    rules_map[rid] = (
                        rule.get('sequence', 999999),
                        rule.get('name', ''),
                        rule.get('rulefield_type', 'float'),
                        bool(rule.get('is_show_sum')),
                    )

        rule_ids_sorted = [rid for rid, _ in sorted(rules_map.items(), key=lambda x: (x[1][0], x[1][1]))]

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(u"Тайлан")

        title_fmt = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 16, 'font_name': 'Arial'
        })
        filter_fmt = workbook.add_format({
            'bold': False, 'align': 'left', 'valign': 'vcenter',
            'font_size': 10, 'font_name': 'Arial'
        })
        header_fmt = workbook.add_format({
            'border': 1, 'bold': True, 'align': 'center', 'valign': 'vcenter',
            'text_wrap': True, 'font_size': 10, 'bg_color': '#E0E0E0', 'font_name': 'Arial'
        })
        dept_fmt = workbook.add_format({
            'border': 1, 'bold': True, 'align': 'left', 'valign': 'vcenter',
            'font_size': 10, 'font_name': 'Arial'
        })
        left_fmt = workbook.add_format({
            'border': 1, 'align': 'left', 'valign': 'vcenter',
            'font_size': 10, 'font_name': 'Arial'
        })
        num_fmt = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter',
            'font_size': 10, 'font_name': 'Arial',
            'num_format': '#,##0.00'
        })
        total_lbl_fmt = workbook.add_format({
            'border': 1, 'bold': True, 'align': 'left', 'valign': 'vcenter',
            'font_size': 10, 'bg_color': '#D9D9D9', 'font_name': 'Arial'
        })
        total_num_fmt = workbook.add_format({
            'border': 1, 'bold': True, 'align': 'right', 'valign': 'vcenter',
            'font_size': 10, 'bg_color': '#D9D9D9', 'font_name': 'Arial',
            'num_format': '#,##0.00'
        })

        start_col = 0
        last_col = start_col + len(rule_ids_sorted)

        file_name = u'Цалингийн тайлан'
        row = 0
        sheet.merge_range(row, start_col, row, last_col, file_name, title_fmt)
        row += 1
        sheet.write(row, start_col, u"Эхлэх хугацаа:" + str(self.start_date), filter_fmt)
        row += 1
        sheet.write(row, start_col, u"Дуусах хугацаа:" + str(self.end_date), filter_fmt)
        row += 2

        sheet.write(row, start_col, u"Ажилтан", header_fmt)
        for i, rid in enumerate(rule_ids_sorted, start=1):
            sheet.write(row, start_col + i, rules_map[rid][1], header_fmt)
        row += 1

        grand_rule_totals = {rid: 0.0 for rid in rule_ids_sorted}

        for payroll in sorted(payrolls.values(), key=itemgetter('payroll_id')):
            dept_name = payroll.get('department_name', u'Тодорхойгүй')

            # Department row (first column only; keep same font size as rest, bold)
            sheet.write(row, start_col, dept_name, dept_fmt)
            for c in range(1, len(rule_ids_sorted) + 1):
                sheet.write(row, start_col + c, '', dept_fmt)
            row += 1

            dept_rule_totals = {rid: 0.0 for rid in rule_ids_sorted}

            employees_sorted = sorted(payroll['employees'].values(), key=lambda e: (e.get('firstname') or ''))
            for emp in employees_sorted:
                sheet.write(row, start_col, "    " + (emp.get('lastname') or u'Тодорхойгүй') + " " + (emp.get('firstname') or u'Тодорхойгүй'), left_fmt)

                for i, rid in enumerate(rule_ids_sorted, start=1):
                    rule = emp['rules'].get(rid)
                    if not rule:
                        sheet.write(row, start_col + i, '', num_fmt)
                        continue

                    rtype = rule.get('rulefield_type')
                    if rtype == 'char':
                        sheet.write(row, start_col + i, rule.get('char_value', ''), left_fmt)
                    else:
                        val = float(rule.get('value') or 0.0)
                        sheet.write_number(row, start_col + i, val, num_fmt)
                        if rule.get('is_show_sum'):
                            dept_rule_totals[rid] += val

                row += 1

            sheet.write(row, start_col, u"Албаны нийт дүн", total_lbl_fmt)
            for i, rid in enumerate(rule_ids_sorted, start=1):
                seq, rname, rtype, show_sum = rules_map[rid]
                if show_sum and rtype != 'char':
                    sheet.write_number(row, start_col + i, dept_rule_totals[rid], total_num_fmt)
                    grand_rule_totals[rid] += dept_rule_totals[rid]
                else:
                    sheet.write(row, start_col + i, '', total_num_fmt)
            row += 1

        sheet.write(row, start_col, u"НИЙТ ДҮН", total_lbl_fmt)
        for i, rid in enumerate(rule_ids_sorted, start=1):
            seq, rname, rtype, show_sum = rules_map[rid]
            if show_sum and rtype != 'char':
                sheet.write_number(row, start_col + i, grand_rule_totals[rid], total_num_fmt)
            else:
                sheet.write(row, start_col + i, '', total_num_fmt)

        # Column widths
        sheet.set_column(start_col, start_col, 35)  # Department/Employee
        if len(rule_ids_sorted) > 0:
            sheet.set_column(start_col + 1, last_col, 18)

        workbook.close()

        data = base64.b64encode(output.getvalue())
        attachment = self.env['ir.attachment'].create({
            'name': f"{file_name}.xlsx",
            'type': 'binary',
            'datas': data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }