# -*- coding: utf-8 -*-

from odoo.tools.translate import _ # type: ignore
from odoo import api, fields, models, _, modules # type: ignore
import xlsxwriter # type: ignore
from io import BytesIO
import base64
import logging
from odoo.exceptions import UserError # type: ignore
_logger = logging.getLogger(__name__)

class LLPPayrollIncomeTaxImport(models.TransientModel):
    _name = 'llp.payroll.income.tax.import'

    start_date = fields.Date(string="Start date")
    end_date = fields.Date(string="End date")
    company_id = fields.Many2one('res.company',string="Company",default=lambda self: self.env.company)
    department_ids = fields.Many2many('hr.department', string="Departments", domain="[('company_id','=',company_id)]", tracking=True)
    export_type = fields.Selection([('excel','Excel')],string="Export type",default="excel")

    def action_export(self):
        self.ensure_one()

        query = """
            SELECT 
                CASE WHEN D.rulefield_type = 'digit' THEN COALESCE(DV.value, 0)::text ELSE COALESCE(DV.char_value, '') END AS civil_number,
                CASE WHEN E.rulefield_type = 'digit' THEN COALESCE(EV.value, 0)::text ELSE COALESCE(EV.char_value, '') END AS register_number,
                CASE WHEN F.rulefield_type = 'digit' THEN COALESCE(FV.value, 0)::text ELSE COALESCE(FV.char_value, '') END AS family_name,
                CASE WHEN G.rulefield_type = 'digit' THEN COALESCE(GV.value, 0)::text ELSE COALESCE(GV.char_value, '') END AS last_name,
                CASE WHEN H.rulefield_type = 'digit' THEN COALESCE(HV.value, 0)::text ELSE COALESCE(HV.char_value, '') END AS first_name,
                CASE WHEN I.rulefield_type = 'digit' THEN COALESCE(IV.value, 0)::text ELSE COALESCE(IV.char_value, '') END AS insurance_type,
                CASE WHEN J.rulefield_type = 'digit' THEN COALESCE(JV.value, 0)::text ELSE COALESCE(JV.char_value, '') END AS citizenship,
                CASE WHEN K.rulefield_type = 'digit' THEN COALESCE(KV.value, 0)::text ELSE COALESCE(KV.char_value, '') END AS wages_and_equivalent_income,
                CASE WHEN L.rulefield_type = 'digit' THEN COALESCE(LV.value, 0)::text ELSE COALESCE(LV.char_value, '') END AS base_and_additional_salary,
                CASE WHEN M.rulefield_type = 'digit' THEN COALESCE(MV.value, 0)::text ELSE COALESCE(MV.char_value, '') END AS bonus_salary,
                CASE WHEN N.rulefield_type = 'digit' THEN COALESCE(NV.value, 0)::text ELSE COALESCE(NV.char_value, '') END AS other_additional_salary,
                CASE WHEN O.rulefield_type = 'digit' THEN COALESCE(OV.value, 0)::text ELSE COALESCE(OV.char_value, '') END AS food_transportation_cost,
                CASE WHEN P.rulefield_type = 'digit' THEN COALESCE(PV.value, 0)::text ELSE COALESCE(PV.char_value, '') END AS firewood_discount,
                CASE WHEN Q.rulefield_type = 'digit' THEN COALESCE(QV.value, 0)::text ELSE COALESCE(QV.char_value, '') END AS career_classification,
                CASE WHEN R.rulefield_type = 'digit' THEN COALESCE(RV.value, 0)::text ELSE COALESCE(RV.char_value, '') END AS cellphone,
                CASE WHEN S.rulefield_type = 'digit' THEN COALESCE(SV.value, 0)::text ELSE COALESCE(SV.char_value, '') END AS email
            FROM llp_payroll A
                LEFT JOIN llp_payroll_line B ON B.payroll_id = A.id
                LEFT JOIN (
                    SELECT *
                    FROM llp_payroll_report_config
                    WHERE type = 'insurance_tax_import'
                    ORDER BY id
                    LIMIT 1
                ) C ON TRUE
                LEFT JOIN llp_payroll_rule D ON D.id = C.civil_number
                LEFT JOIN llp_payroll_rule_value DV ON DV.payroll_rule_id = D.id AND B.id = DV.line_id
                LEFT JOIN llp_payroll_rule E ON E.id = C.register_number
                LEFT JOIN llp_payroll_rule_value EV ON EV.payroll_rule_id = E.id AND B.id = EV.line_id
                LEFT JOIN llp_payroll_rule F ON F.id = C.family_name
                LEFT JOIN llp_payroll_rule_value FV ON FV.payroll_rule_id = F.id AND B.id = FV.line_id
                LEFT JOIN llp_payroll_rule G ON G.id = C.last_name
                LEFT JOIN llp_payroll_rule_value GV ON GV.payroll_rule_id = G.id AND B.id = GV.line_id
                LEFT JOIN llp_payroll_rule H ON H.id = C.first_name
                LEFT JOIN llp_payroll_rule_value HV ON HV.payroll_rule_id = H.id AND B.id = HV.line_id
                LEFT JOIN llp_payroll_rule I ON I.id = C.insurance_type
                LEFT JOIN llp_payroll_rule_value IV ON IV.payroll_rule_id = I.id AND B.id = IV.line_id
                LEFT JOIN llp_payroll_rule J ON J.id = C.citizenship
                LEFT JOIN llp_payroll_rule_value JV ON JV.payroll_rule_id = J.id AND B.id = JV.line_id
                LEFT JOIN llp_payroll_rule K ON K.id = C.wages_and_equivalent_income
                LEFT JOIN llp_payroll_rule_value KV ON KV.payroll_rule_id = K.id AND B.id = KV.line_id
                LEFT JOIN llp_payroll_rule L ON L.id = C.base_and_additional_salary
                LEFT JOIN llp_payroll_rule_value LV ON LV.payroll_rule_id = L.id AND B.id = LV.line_id
                LEFT JOIN llp_payroll_rule M ON M.id = C.bonus_salary
                LEFT JOIN llp_payroll_rule_value MV ON MV.payroll_rule_id = M.id AND B.id = MV.line_id
                LEFT JOIN llp_payroll_rule N ON N.id = C.other_additional_salary
                LEFT JOIN llp_payroll_rule_value NV ON NV.payroll_rule_id = N.id AND B.id = NV.line_id
                LEFT JOIN llp_payroll_rule O ON O.id = C.food_transportation_cost
                LEFT JOIN llp_payroll_rule_value OV ON OV.payroll_rule_id = O.id AND B.id = OV.line_id
                LEFT JOIN llp_payroll_rule P ON P.id = C.firewood_discount
                LEFT JOIN llp_payroll_rule_value PV ON PV.payroll_rule_id = P.id AND B.id = PV.line_id
                LEFT JOIN llp_payroll_rule Q ON Q.id = C.career_classification
                LEFT JOIN llp_payroll_rule_value QV ON QV.payroll_rule_id = Q.id AND B.id = QV.line_id
                LEFT JOIN llp_payroll_rule R ON R.id = C.cellphone
                LEFT JOIN llp_payroll_rule_value RV ON RV.payroll_rule_id = R.id AND B.id = RV.line_id
                LEFT JOIN llp_payroll_rule S ON S.id = C.email
                LEFT JOIN llp_payroll_rule_value SV ON SV.payroll_rule_id = S.id AND B.id = SV.line_id
                LEFT JOIN llp_payroll_structure T ON T.id = A.struct_id
            WHERE A.state = 'confirmed'
            AND T.struct_type = 'salary_late'
            AND A.start_date = %s
            AND A.end_date   = %s
        """
        params = [self.start_date, self.end_date]

        if self.department_ids:
            query += " AND A.department_id IN %s"
            params.append(tuple(self.department_ids.ids))

        self.env.cr.execute(query, tuple(params))
        cols = [d[0] for d in self.env.cr.description]
        rows = self.env.cr.fetchall()

        if not rows:
            raise UserError("Өгөгдөл олдсонгүй.")

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

        sheet.write(0, 0, u'Иргэний дугаар', header_fmt)
        sheet.write(0, 1, u'Регистрийн дугаар', header_fmt)
        sheet.write(0, 2, u'Ургийн овог', header_fmt)
        sheet.write(0, 3, u'Эцэг/эхийн нэр', header_fmt)
        sheet.write(0, 4, u'Нэр', header_fmt)
        sheet.write(0, 5, u'Даатгуулагчийн төрөл', header_fmt)
        sheet.write(0, 6, u'Иргэншил', header_fmt)
        sheet.write(0, 7, u'Хөдөлмөрийн хөлс түүнтэй адилтгах орлого', header_fmt)
        sheet.write(0, 8, u'Үндсэн ба нэмэгдэл цалин', header_fmt)
        sheet.write(0, 9, u'Шагналт цалин', header_fmt)
        sheet.write(0, 10, u'Бусад нэмэгдэл цалин', header_fmt)
        sheet.write(0, 11, u'Хоол унааны хөлс', header_fmt)
        sheet.write(0, 12, u'Түлээ нүүрсний үнийн хөнгөлөлт', header_fmt)
        sheet.write(0, 13, u'Ажил мэргэжлийн ангилал', header_fmt)
        sheet.write(0, 14, u'Харилцах утасны дугаар', header_fmt)
        sheet.write(0, 15, u'Цахим шуудангийн хаяг', header_fmt)

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
        file_name = u'Нийгмийн даатгал руу ИМПОРТ хийх загвар'
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