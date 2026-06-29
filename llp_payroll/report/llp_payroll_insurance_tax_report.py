# -*- coding: utf-8 -*-

from odoo.tools.translate import _ # type: ignore
from odoo import api, fields, models, _, modules # type: ignore
import xlsxwriter # type: ignore
from io import BytesIO
import base64
import logging
from odoo.exceptions import UserError # type: ignore
_logger = logging.getLogger(__name__)

class LLPPayrollInsuranceTaxReport(models.TransientModel):
    _name = 'llp.payroll.insurance.tax.report'

    start_date = fields.Date(string="Start date")
    end_date = fields.Date(string="End date")
    company_id = fields.Many2one('res.company',string="Company",default=lambda self: self.env.company)
    department_ids = fields.Many2many('hr.department', string="Departments", domain="[('company_id','=',company_id)]", tracking=True)
    export_type = fields.Selection([('excel','Excel')],string="Export type",default="excel")

    def action_export(self):
        self.ensure_one()

        query = """
            SELECT 
                P.id AS company_id, P.name AS company_name,
                O.id AS department_id, O.complete_name as department_name,
                B.employee_id,
                CASE WHEN D.rulefield_type = 'digit' THEN COALESCE(DV.value, 0)::text ELSE COALESCE(DV.char_value, '') END AS civil_number,
                CASE WHEN E.rulefield_type = 'digit' THEN COALESCE(EV.value, 0)::text ELSE COALESCE(EV.char_value, '') END AS lastname,
                CASE WHEN F.rulefield_type = 'digit' THEN COALESCE(FV.value, 0)::text ELSE COALESCE(FV.char_value, '') END AS firstname,
                CASE WHEN G.rulefield_type = 'digit' THEN COALESCE(GV.value, 0)::text ELSE COALESCE(GV.char_value, '') END AS job,
                CASE WHEN H.rulefield_type = 'digit' THEN COALESCE(HV.value, 0)::text ELSE COALESCE(HV.char_value, '') END AS wages_and_equivalent_income,
                CASE WHEN I.rulefield_type = 'digit' THEN COALESCE(IV.value, 0)::text ELSE COALESCE(IV.char_value, '') END AS insurance_tax_employer,
                CASE WHEN J.rulefield_type = 'digit' THEN COALESCE(JV.value, 0)::text ELSE COALESCE(JV.char_value, '') END AS insurance_tax_employee,
                CASE WHEN K.rulefield_type = 'digit' THEN COALESCE(KV.value, 0)::text ELSE COALESCE(KV.char_value, '') END AS insurance_type,
                CASE WHEN L.rulefield_type = 'digit' THEN COALESCE(LV.value, 0)::text ELSE COALESCE(LV.char_value, '') END AS is_limit_max
            FROM llp_payroll A
                LEFT JOIN llp_payroll_line B ON B.payroll_id = A.id
                LEFT JOIN (
                    SELECT *
                    FROM llp_payroll_report_config
                    WHERE type = 'insurance_tax_report'
                    ORDER BY id
                    LIMIT 1
                ) C ON TRUE
                LEFT JOIN llp_payroll_rule D ON D.id = C.civil_number
                LEFT JOIN llp_payroll_rule_value DV ON DV.payroll_rule_id = D.id AND B.id = DV.line_id
                LEFT JOIN llp_payroll_rule E ON E.id = C.last_name
                LEFT JOIN llp_payroll_rule_value EV ON EV.payroll_rule_id = E.id AND B.id = EV.line_id
                LEFT JOIN llp_payroll_rule F ON F.id = C.first_name
                LEFT JOIN llp_payroll_rule_value FV ON FV.payroll_rule_id = F.id AND B.id = FV.line_id
                LEFT JOIN llp_payroll_rule G ON G.id = C.job
                LEFT JOIN llp_payroll_rule_value GV ON GV.payroll_rule_id = G.id AND B.id = GV.line_id
                LEFT JOIN llp_payroll_rule H ON H.id = C.insurance_type
                LEFT JOIN llp_payroll_rule_value HV ON HV.payroll_rule_id = H.id AND B.id = HV.line_id
                LEFT JOIN llp_payroll_rule I ON I.id = C.wages_and_equivalent_income
                LEFT JOIN llp_payroll_rule_value IV ON IV.payroll_rule_id = I.id AND B.id = IV.line_id
                LEFT JOIN llp_payroll_rule J ON J.id = C.insurance_tax_employer
                LEFT JOIN llp_payroll_rule_value JV ON JV.payroll_rule_id = J.id AND B.id = JV.line_id
                LEFT JOIN llp_payroll_rule K ON K.id = C.insurance_tax_employee
                LEFT JOIN llp_payroll_rule_value KV ON KV.payroll_rule_id = K.id AND B.id = KV.line_id
                LEFT JOIN llp_payroll_rule L ON L.id = C.is_limit_max
                LEFT JOIN llp_payroll_rule_value LV ON LV.payroll_rule_id = L.id AND B.id = LV.line_id
                LEFT JOIN llp_payroll_structure M ON M.id = A.struct_id
                LEFT JOIN hr_employee N ON N.id = B.employee_id
                LEFT JOIN hr_department O ON O.id = N.department_id
                LEFT JOIN res_company P ON P.id = O.company_id
            WHERE A.state = 'confirmed' 
            AND M.struct_type = 'salary_late'
            AND A.start_date = %s
            AND A.end_date   = %s
        """
        params = [self.start_date, self.end_date]

        if self.department_ids:
            query += " AND A.department_id IN %s"
            params.append(tuple(self.department_ids.ids))

        self.env.cr.execute(query, tuple(params))
        cols = [d[0] for d in self.env.cr.description]
        rows = [dict(zip(cols, r)) for r in self.env.cr.fetchall()]
        if not rows:
            raise UserError("Өгөгдөл олдсонгүй.")
        
        companies = {}
        for dic in rows:
            company_id = dic['company_id']
            if company_id not in companies:
                companies[company_id] = {
                    'company_id': company_id,
                    'department_id': dic.get('department_id', 0),
                    'department_name': dic.get('department_name') or u'Тодорхойгүй',
                    'departments': {},
                }

            department_id = dic['department_id']
            if department_id not in companies[company_id]['departments']:
                companies[company_id]['departments'][department_id] = {
                    'department_id': department_id,
                    'department_name': dic.get('department_name') or u'Тодорхойгүй',
                    'employees': {},
                }

            employee_id = dic['employee_id']
            companies[company_id]['departments'][department_id]['employees'][employee_id] = {
                'employee_id': employee_id,
                'firstname': dic.get('firstname') or u'Тодорхойгүй',
                'lastname': dic.get('lastname') or u'Тодорхойгүй',
                'rules': {},
            }

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Тайлан")

        header_fmt = workbook.add_format({
            'bold': True, 
            'border': 1, 
            'align': 'center', 
            'bg_color': "#B0E7E7", 
            'text_wrap': True, 
            'valign': 'vcenter'
        })

        cell_fmt = workbook.add_format({
            'border': 1
        })

        num_fmt = workbook.add_format({
            'border': 1,
            'num_format': '#,##0.00'
        })


        start_col = 0
        last_col = start_col + len(rule_ids_sorted)

        row = 0
        sheet.merge_range(row, start_col, row, last_col, file_name, title_fmt)
        row += 1
        sheet.write(row, start_col, u"Эхлэх хугацаа:" + str(self.start_date), filter_fmt)
        row += 1
        sheet.write(row, start_col, u"Дуусах хугацаа:" + str(self.end_date), filter_fmt)
        row += 2

        sheet.write(3, 0, u'Овог', header_fmt)
        sheet.write(3, 1, u'Нэр', header_fmt)
        sheet.write(3, 2, u'Албан тушаал', header_fmt)
        sheet.write(3, 3, u'Иргэний дугаар', header_fmt)
        sheet.write(3, 4, u'Хөдөлмөрийн хөлс, түүнтэй адилтгах орлого /төгрөгөөр/', header_fmt)
        sheet.write(3, 5, u'Нийгмийн даатгалын санд төлөх шимтгэл /төгрөгөөр/ - Ажил олгогч', header_fmt)
        sheet.write(3, 6, u'Нийгмийн даатгалын санд төлөх шимтгэл /төгрөгөөр/ - Даатгуулагч', header_fmt)
        sheet.write(3, 7, u'Даатгуулагчийн төрөл', header_fmt)
        sheet.write(3, 8, u'Дээд хэмжээ хязгаарлах эсэх', header_fmt)

        for row_idx, row in enumerate(rows, start=1):
            for col_idx, value in enumerate(row):
                if isinstance(value, (int, float)):
                    sheet.write_number(row_idx, col_idx, value, num_fmt)
                else:
                    sheet.write(row_idx, col_idx, value or '', cell_fmt)

        for i in range(len(cols)):
            sheet.set_column(i, i, 20)

        workbook.close()

        data = base64.b64encode(output.getvalue())
        file_name = u'Нийгмийн даатгал шимтгэлийн хураамжийн тайлан'
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