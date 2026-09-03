# -*- coding: utf-8 -*-

from odoo.tools.translate import _ # type: ignore
from odoo import api, fields, models, _, modules # type: ignore
import xlsxwriter # type: ignore
from io import BytesIO
import base64
import logging
from odoo.exceptions import UserError # type: ignore
_logger = logging.getLogger(__name__)


def _clean_value(val):
    """
    None, boolean False, эсвэл 'False' гэсэн текст (str) утга ирвэл
    бүгдийг нь хоосон мөр болгож буцаана. Ингэснээр Excel руу export хийхэд
    хоосон байх ёстой нүд 'False' гэж харагдахгүй.
    """
    if val is None or val is False:
        return ''
    if isinstance(val, str) and val.strip().lower() == 'false':
        return ''
    return val


class LLPPayrollInsuranceImport(models.TransientModel):
    _name = 'llp.payroll.insurance.import'

    start_date = fields.Date(string="Start date")
    end_date = fields.Date(string="End date")
    company_id = fields.Many2one('res.company',string="Company",default=lambda self: self.env.company)
    department_ids = fields.Many2many('hr.department', string="Departments", domain="[('company_id','=',company_id)]", tracking=True)
    export_type = fields.Selection([('excel','Excel')],string="Export type",default="excel")

    def action_export(self):
        self.ensure_one()

        has_department = bool(self.department_ids)

        department_select = """
            COALESCE(HD.name->>'mn_MN', HD.name->>'en_US', '') AS department_name,
        """

        query = f"""
            SELECT 
                {department_select}
                CASE WHEN E.rulefield_type = 'digit' THEN COALESCE(EV.value, 0) END AS register_number_num,
                CASE WHEN E.rulefield_type != 'digit' THEN COALESCE(EV.char_value, '') END AS register_number_char,

                CASE WHEN F.rulefield_type = 'digit' THEN COALESCE(FV.value, 0) END AS family_name_num,
                CASE WHEN F.rulefield_type != 'digit' THEN COALESCE(FV.char_value, '') END AS family_name_char,

                CASE WHEN G.rulefield_type = 'digit' THEN COALESCE(GV.value, 0) END AS last_name_num,
                CASE WHEN G.rulefield_type != 'digit' THEN COALESCE(GV.char_value, '') END AS last_name_char,

                CASE WHEN H.rulefield_type = 'digit' THEN COALESCE(HV.value, 0) END AS first_name_num,
                CASE WHEN H.rulefield_type != 'digit' THEN COALESCE(HV.char_value, '') END AS first_name_char,

                CASE WHEN I.rulefield_type = 'digit' THEN COALESCE(IV.value, 0) END AS insurance_type_num,
                CASE WHEN I.rulefield_type != 'digit' THEN COALESCE(IV.char_value, '') END AS insurance_type_char,

                CASE WHEN Q.rulefield_type = 'digit' THEN COALESCE(QV.value, 0) END AS career_classification_num,
                CASE WHEN Q.rulefield_type != 'digit' THEN COALESCE(QV.char_value, '') END AS career_classification_char,

                CASE WHEN K.rulefield_type = 'digit' THEN COALESCE(KV.value, 0) END AS wages_and_equivalent_income_num,
                CASE WHEN K.rulefield_type != 'digit' THEN COALESCE(KV.char_value, '') END AS wages_and_equivalent_income_char,

                CASE WHEN L.rulefield_type = 'digit' THEN COALESCE(LV.value, 0) END AS base_and_additional_salary_num,
                CASE WHEN L.rulefield_type != 'digit' THEN COALESCE(LV.char_value, '') END AS base_and_additional_salary_char,

                CASE WHEN M.rulefield_type = 'digit' THEN COALESCE(MV.value, 0) END AS bonus_salary_num,
                CASE WHEN M.rulefield_type != 'digit' THEN COALESCE(MV.char_value, '') END AS bonus_salary_char,

                CASE WHEN N.rulefield_type = 'digit' THEN COALESCE(NV.value, 0) END AS other_additional_salary_num,
                CASE WHEN N.rulefield_type != 'digit' THEN COALESCE(NV.char_value, '') END AS other_additional_salary_char,

                CASE WHEN O.rulefield_type = 'digit' THEN COALESCE(OV.value, 0) END AS food_transportation_cost_num,
                CASE WHEN O.rulefield_type != 'digit' THEN COALESCE(OV.char_value, '') END AS food_transportation_cost_char,

                CASE WHEN P.rulefield_type = 'digit' THEN COALESCE(PV.value, 0) END AS firewood_discount_num,
                CASE WHEN P.rulefield_type != 'digit' THEN COALESCE(PV.char_value, '') END AS firewood_discount_char,

                CASE WHEN J.rulefield_type = 'digit' THEN COALESCE(JV.value, 0) END AS citizenship_num,
                CASE WHEN J.rulefield_type != 'digit' THEN COALESCE(JV.char_value, '') END AS citizenship_char,

                CASE WHEN R.rulefield_type = 'digit' THEN COALESCE(RV.value, 0) END AS cellphone_num,
                CASE WHEN R.rulefield_type != 'digit' THEN COALESCE(RV.char_value, '') END AS cellphone_char,

                CASE WHEN S.rulefield_type = 'digit' THEN COALESCE(SV.value, 0) END AS email_num,
                CASE WHEN S.rulefield_type != 'digit' THEN COALESCE(SV.char_value, '') END AS email_char

            FROM llp_payroll A
                LEFT JOIN llp_payroll_line B ON B.payroll_id = A.id
                LEFT JOIN hr_employee EMP ON EMP.id = B.employee_id
                LEFT JOIN hr_department HD ON HD.id = EMP.department_id
                LEFT JOIN (
                    SELECT *
                    FROM llp_payroll_report_config
                    WHERE type = 'insurance_tax_import'
                    ORDER BY id
                    LIMIT 1
                ) C ON TRUE
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
                LEFT JOIN llp_payroll_rule Q ON Q.id = C.career_classification
                LEFT JOIN llp_payroll_rule_value QV ON QV.payroll_rule_id = Q.id AND B.id = QV.line_id
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
                LEFT JOIN llp_payroll_rule J ON J.id = C.citizenship
                LEFT JOIN llp_payroll_rule_value JV ON JV.payroll_rule_id = J.id AND B.id = JV.line_id
                LEFT JOIN llp_payroll_rule R ON R.id = C.cellphone
                LEFT JOIN llp_payroll_rule_value RV ON RV.payroll_rule_id = R.id AND B.id = RV.line_id
                LEFT JOIN llp_payroll_rule S ON S.id = C.email
                LEFT JOIN llp_payroll_rule_value SV ON SV.payroll_rule_id = S.id AND B.id = SV.line_id
                LEFT JOIN llp_payroll_structure T ON T.id = A.struct_id
            WHERE A.state = 'confirmed'
            AND T.struct_type = 'salary_late'
            AND A.start_date = %s
            AND A.end_date   = %s
            AND A.company_id = %s
        """
        params = [self.start_date, self.end_date, self.company_id.id]

        if has_department:
            # ЗАСВАР: batch-ийн department биш, АЖИЛТНЫ ӨӨРИЙНХ НЬ department-ээр filter хийнэ
            query += " AND EMP.department_id IN %s"
            params.append(tuple(self.department_ids.ids))

        query += " ORDER BY department_name, A.id"

        self.env.cr.execute(query, tuple(params))
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

        cell_fmt = workbook.add_format({'border': 1})

        num_fmt = workbook.add_format({
            'border': 1,
            'num_format': '#,##0.00'
        })

        dept_fmt = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })

        bold_num_fmt = workbook.add_format({
            'border': 1,
            'bold': True,
            'num_format': '#,##0.00'
        })
        bold_label_fmt = workbook.add_format({
            'border': 1,
            'bold': True,
            'align': 'center',
            'valign': 'vcenter'
        })

        # ЗАСВАР: department багана одоо ЯМАГТ гарна (department_ids сонгосон эсэхээс үл хамааран),
        # учир нь одоо энэ бол ажилтны бодит хэлтэс, тайланд байх ёстой мэдээлэл
        headers = [u'Алба']
        headers += [
            u'Регистрийн дугаар',
            u'Ургийн овог',
            u'Эцэг/эхийн нэр',
            u'Нэр',
            u'Даатгуулагчийн төрөл',
            u'Ажил мэргэжлийн ангилал',
            u'Хөдөлмөрийн хөлс түүнтэй адилтгах орлого',
            u'Үндсэн ба нэмэгдэл цалин',
            u'Шагналт цалин',
            u'Бусад нэмэгдэл цалин',
            u'Хоол унааны хөлс',
            u'Түлээ нүүрсний үнийн хөнгөлөлт',
            u'Иргэншил',
            u'Харилцах утасны дугаар',
            u'Цахим шуудангийн хаяг',
        ]

        for col_idx, header in enumerate(headers):
            sheet.write(0, col_idx, header, header_fmt)
        sheet.set_row(0, 40)

        dept_offset = 1
        field_count = 15

        for row_idx, row in enumerate(rows, start=1):
            # ЗАСВАР: хэлтэсийн нэр хоосон/None/'False' ирвэл '' болгож бичнэ
            sheet.write(row_idx, 0, _clean_value(row[0]), cell_fmt)

            for i in range(field_count):
                num_val = row[dept_offset + i * 2]
                char_val = row[dept_offset + i * 2 + 1]
                col_idx = dept_offset + i
                if num_val is not None:
                    sheet.write_number(row_idx, col_idx, float(num_val), num_fmt)
                else:
                    # ЗАСВАР: char утга None/False/'False' ирвэл '' болгож бичнэ
                    sheet.write(row_idx, col_idx, _clean_value(char_val), cell_fmt)

        # 2. Дараа нь "Нийт" мөрийг ГАДНА, ТУСДАА нэг л удаа бичнэ
        total_row_idx = len(rows) + 1
        sheet.write(total_row_idx, 0, u'Нийт', bold_label_fmt)

        for i in range(field_count):
            col_idx = dept_offset + i
            values = [row[dept_offset + i * 2] for row in rows]
            if any(v is not None for v in values):
                total = sum(float(v) for v in values if v is not None)
                sheet.write_number(total_row_idx, col_idx, total, bold_num_fmt)
            else:
                sheet.write(total_row_idx, col_idx, '', cell_fmt)

        # Department баганыг ижил утгаараа бүлэглэн merge хийх (одоо ажилтны бодит department-ээр)
        dept_col = 0
        start_row = 1
        current_dept = rows[0][0]

        def write_dept_block(s_row, e_row, dept_value):
            # ЗАСВАР: None/False/'False' ирвэл '' болгож бичнэ
            dept_value = _clean_value(dept_value)
            if e_row > s_row:
                sheet.merge_range(s_row, dept_col, e_row, dept_col, dept_value, dept_fmt)
            else:
                sheet.write(s_row, dept_col, dept_value, dept_fmt)

        for row_idx, row in enumerate(rows[1:], start=2):
            dept = row[0]
            if dept != current_dept:
                write_dept_block(start_row, row_idx - 1, current_dept)
                current_dept = dept
                start_row = row_idx

        write_dept_block(start_row, len(rows), current_dept)

        for i in range(len(headers)):
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