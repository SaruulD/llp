# -*- coding: utf-8 -*-

from odoo.tools.translate import _
from odoo import api, fields, models, _, modules
from datetime import datetime,timedelta
from operator import itemgetter
import pdfkit
import xlsxwriter
from io import BytesIO
import base64
import logging
from odoo.exceptions import UserError
from collections import defaultdict

_logger = logging.getLogger(__name__)

class LLPPayrollBankReport(models.TransientModel):
    _name = 'llp.payroll.bank.report'

    start_date = fields.Date(string="Start date")
    end_date = fields.Date(string="End date")
    department_ids = fields.Many2many('hr.department', string="Departments", tracking=True)
    export_type = fields.Selection([('excel','Excel')],string="Export type",default="excel")
    struct_id = fields.Many2one('llp.payroll.structure',string="Stucture", domain="[('state','=','done')]",tracking=True)
    
    def action_export(self):
        self.ensure_one()

        query = """
            SELECT
                C.name AS struct_name,
                A.id AS payroll_id,
                A.department_id AS department_id,
                H.complete_name AS department_name,
                B.employee_id AS employee_id,
                G.first_name AS first_name,
                G.last_name AS last_name,
                E.id AS rule_id,
                E.name AS rule_name,
                COALESCE(F.value, 0) AS value,
                I.acc_number AS account_number,
                J.name AS bank
            FROM llp_payroll A
                LEFT JOIN llp_payroll_line B ON B.payroll_id = A.id
                LEFT JOIN llp_payroll_structure C ON C.id = A.struct_id
                LEFT JOIN llp_payroll_structure_line D ON D.struct_id = C.id
                INNER JOIN llp_payroll_rule E
                    ON E.id = D.rule_id AND E.is_net_amount = true
                LEFT JOIN llp_payroll_rule_value F
                    ON F.payroll_rule_id = E.id AND B.id = F.line_id
                LEFT JOIN hr_employee G ON G.id = B.employee_id
                LEFT JOIN hr_department H ON H.id = A.department_id
                LEFT JOIN res_partner_bank I ON I.id = G.bank_account_id
                LEFT JOIN res_bank J ON J.id = I.bank_id
            WHERE A.state = 'confirmed'
            AND A.start_date = %s
            AND A.end_date   = %s
            AND C.id         = %s
        """
        params = [self.start_date, self.end_date, self.struct_id.id]

        if self.department_ids:
            query += " AND A.department_id IN %s"
            params.append(tuple(self.department_ids.ids))

        query += " ORDER BY J.name, G.last_name, G.first_name"

        self.env.cr.execute(query, tuple(params))
        cols = [d[0] for d in self.env.cr.description]
        rows = [dict(zip(cols, r)) for r in self.env.cr.fetchall()]
        if not rows:
            raise UserError("No data found for selected filters.")

        struct_name = rows[0].get('struct_name') or (self.struct_id.name or '')

        by_bank = defaultdict(list)
        for r in rows:
            bank_name = (r.get('bank') or 'Unknown Bank').strip()
            by_bank[bank_name].append(r)

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        title_fmt = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 14, 'font_name': 'Arial'
        })
        filter_fmt = workbook.add_format({
            'bold': False, 'align': 'left', 'valign': 'vcenter',
            'font_size': 10, 'font_name': 'Arial'
        })
        header_fmt = workbook.add_format({
            'border': 1, 'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 10, 'bg_color': '#E0E0E0', 'font_name': 'Arial'
        })
        text_fmt = workbook.add_format({
            'border': 1, 'align': 'left', 'valign': 'vcenter',
            'font_size': 10, 'font_name': 'Arial'
        })
        num_fmt = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter',
            'font_size': 10, 'font_name': 'Arial',
            'num_format': '#,##0.00'
        })
        total_lbl_fmt = workbook.add_format({
            'border': 1, 'bold': True, 'align': 'right', 'valign': 'vcenter',
            'font_size': 10, 'bg_color': '#D9D9D9', 'font_name': 'Arial'
        })
        total_num_fmt = workbook.add_format({
            'border': 1, 'bold': True, 'align': 'right', 'valign': 'vcenter',
            'font_size': 10, 'bg_color': '#D9D9D9', 'font_name': 'Arial',
            'num_format': '#,##0.00'
        })

        def _safe_sheet_name(name, used):
            bad = [':', '\\', '/', '?', '*', '[', ']']
            for ch in bad:
                name = name.replace(ch, ' ')
            name = (name or 'Sheet').strip()[:31] or 'Sheet'
            base = name
            i = 2
            while name in used:
                suffix = f" {i}"
                name = (base[:31 - len(suffix)] + suffix)
                i += 1
            used.add(name)
            return name

        used = set()

        for bank_name, bank_rows in sorted(by_bank.items(), key=lambda x: x[0].lower()):
            sheet_name = _safe_sheet_name(bank_name, used)
            sheet = workbook.add_worksheet(sheet_name)

            sheet.set_column(0, 0, 18)
            sheet.set_column(1, 1, 18)
            sheet.set_column(2, 2, 26)
            sheet.set_column(3, 3, 16)

            row = 0
            sheet.merge_range(row, 0, row, 3, struct_name, title_fmt)
            row += 1
            sheet.write(row, 0, u"Эхлэх хугацаа: " + str(self.start_date or ''), filter_fmt)
            row += 1
            sheet.write(row, 0, u"Дуусах хугацаа: " + str(self.end_date or ''), filter_fmt)
            row += 2

            sheet.write(row, 0, u"Овог", header_fmt)
            sheet.write(row, 1, u"Нэр", header_fmt)
            sheet.write(row, 2, u"Данс", header_fmt)
            sheet.write(row, 3, u"Дүн", header_fmt)
            row += 1

            total = 0.0

            bank_rows_sorted = sorted(
                bank_rows,
                key=lambda r: ((r.get('last_name') or ''), (r.get('first_name') or ''), (r.get('account_number') or ''))
            )

            for r in bank_rows_sorted:
                last_name = r.get('last_name') or ''
                first_name = r.get('first_name') or ''
                account_number = r.get('account_number') or ''
                value = float(r.get('value') or 0.0)

                total += value

                sheet.write(row, 0, last_name, text_fmt)
                sheet.write(row, 1, first_name, text_fmt)
                sheet.write(row, 2, account_number, text_fmt)
                sheet.write_number(row, 3, value, num_fmt)
                row += 1

            sheet.write(row, 0, "", total_lbl_fmt)
            sheet.write(row, 1, "", total_lbl_fmt)
            sheet.write(row, 2, u"НИЙТ", total_lbl_fmt)
            sheet.write_number(row, 3, total, total_num_fmt)

        workbook.close()

        file_name = u'Банк тайлан'
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