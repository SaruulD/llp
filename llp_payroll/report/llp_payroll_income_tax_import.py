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

        has_department = bool(self.department_ids)

        department_select = """
            COALESCE(HD.name->>'mn_MN', HD.name->>'en_US', '') AS department_name,
        """

        query = f"""
            SELECT 
                {department_select}
                CASE WHEN RA.rulefield_type = 'digit' THEN COALESCE(VA.value, 0) END AS taxpayer_number_num,
                CASE WHEN RA.rulefield_type != 'digit' THEN COALESCE(VA.char_value, '') END AS taxpayer_number_char,

                CASE WHEN RLN.rulefield_type = 'digit' THEN COALESCE(VLN.value, 0) END AS last_name_num,
                CASE WHEN RLN.rulefield_type != 'digit' THEN COALESCE(VLN.char_value, '') END AS last_name_char,

                CASE WHEN RFN.rulefield_type = 'digit' THEN COALESCE(VFN.value, 0) END AS first_name_num,
                CASE WHEN RFN.rulefield_type != 'digit' THEN COALESCE(VFN.char_value, '') END AS first_name_char,

                CASE WHEN RB.rulefield_type = 'digit' THEN COALESCE(VB.value, 0) END AS income_7_1_1_num,
                CASE WHEN RB.rulefield_type != 'digit' THEN COALESCE(VB.char_value, '') END AS income_7_1_1_char,

                CASE WHEN RC.rulefield_type = 'digit' THEN COALESCE(VC.value, 0) END AS income_7_1_2_7_num,
                CASE WHEN RC.rulefield_type != 'digit' THEN COALESCE(VC.char_value, '') END AS income_7_1_2_7_char,

                CASE WHEN RD.rulefield_type = 'digit' THEN COALESCE(VD.value, 0) END AS income_7_1_6_num,
                CASE WHEN RD.rulefield_type != 'digit' THEN COALESCE(VD.char_value, '') END AS income_7_1_6_char,

                CASE WHEN RE.rulefield_type = 'digit' THEN COALESCE(VE.value, 0) END AS total_income_1_2_3_num,
                CASE WHEN RE.rulefield_type != 'digit' THEN COALESCE(VE.char_value, '') END AS total_income_1_2_3_char,

                CASE WHEN RF.rulefield_type = 'digit' THEN COALESCE(VF.value, 0) END AS insurance_rate_num,
                CASE WHEN RF.rulefield_type != 'digit' THEN COALESCE(VF.char_value, '') END AS insurance_rate_char,

                CASE WHEN RG.rulefield_type = 'digit' THEN COALESCE(VG.value, 0) END AS insurance_amount_main_num,
                CASE WHEN RG.rulefield_type != 'digit' THEN COALESCE(VG.char_value, '') END AS insurance_amount_main_char,

                CASE WHEN RH.rulefield_type = 'digit' THEN COALESCE(VH.value, 0) END AS insurance_amount_7_1_6_num,
                CASE WHEN RH.rulefield_type != 'digit' THEN COALESCE(VH.char_value, '') END AS insurance_amount_7_1_6_char,

                CASE WHEN RI.rulefield_type = 'digit' THEN COALESCE(VI.value, 0) END AS taxable_income_num,
                CASE WHEN RI.rulefield_type != 'digit' THEN COALESCE(VI.char_value, '') END AS taxable_income_char,

                CASE WHEN RJ.rulefield_type = 'digit' THEN COALESCE(VJ.value, 0) END AS income_type_num,
                CASE WHEN RJ.rulefield_type != 'digit' THEN COALESCE(VJ.char_value, '') END AS income_type_char,

                CASE WHEN RK.rulefield_type = 'digit' THEN COALESCE(VK.value, 0) END AS income_amount_num,
                CASE WHEN RK.rulefield_type != 'digit' THEN COALESCE(VK.char_value, '') END AS income_amount_char,

                CASE WHEN RL.rulefield_type = 'digit' THEN COALESCE(VL.value, 0) END AS total_taxable_income_num,
                CASE WHEN RL.rulefield_type != 'digit' THEN COALESCE(VL.char_value, '') END AS total_taxable_income_char,

                CASE WHEN RM.rulefield_type = 'digit' THEN COALESCE(VM.value, 0) END AS tax_bracket_num,
                CASE WHEN RM.rulefield_type != 'digit' THEN COALESCE(VM.char_value, '') END AS tax_bracket_char,

                CASE WHEN RN.rulefield_type = 'digit' THEN COALESCE(VN.value, 0) END AS tax_calculated_num,
                CASE WHEN RN.rulefield_type != 'digit' THEN COALESCE(VN.char_value, '') END AS tax_calculated_char,

                CASE WHEN RO.rulefield_type = 'digit' THEN COALESCE(VO.value, 0) END AS months_worked_num,
                CASE WHEN RO.rulefield_type != 'digit' THEN COALESCE(VO.char_value, '') END AS months_worked_char,

                CASE WHEN RP.rulefield_type = 'digit' THEN COALESCE(VP.value, 0) END AS discount_monthly_num,
                CASE WHEN RP.rulefield_type != 'digit' THEN COALESCE(VP.char_value, '') END AS discount_monthly_char,

                CASE WHEN RQ.rulefield_type = 'digit' THEN COALESCE(VQ.value, 0) END AS discount_total_num,
                CASE WHEN RQ.rulefield_type != 'digit' THEN COALESCE(VQ.char_value, '') END AS discount_total_char,

                CASE WHEN RR.rulefield_type = 'digit' THEN COALESCE(VR.value, 0) END AS tax_after_discount_7_1_1_num,
                CASE WHEN RR.rulefield_type != 'digit' THEN COALESCE(VR.char_value, '') END AS tax_after_discount_7_1_1_char,

                CASE WHEN RS.rulefield_type = 'digit' THEN COALESCE(VS.value, 0) END AS tax_7_1_6_num,
                CASE WHEN RS.rulefield_type != 'digit' THEN COALESCE(VS.char_value, '') END AS tax_7_1_6_char,

                CASE WHEN RT.rulefield_type = 'digit' THEN COALESCE(VT.value, 0) END AS total_tax_withheld_num,
                CASE WHEN RT.rulefield_type != 'digit' THEN COALESCE(VT.char_value, '') END AS total_tax_withheld_char,

                CASE WHEN RU.rulefield_type = 'digit' THEN COALESCE(VU.value, 0) END AS annual_discount_diff_num,
                CASE WHEN RU.rulefield_type != 'digit' THEN COALESCE(VU.char_value, '') END AS annual_discount_diff_char,

                CASE WHEN RV.rulefield_type = 'digit' THEN COALESCE(VV.value, 0) END AS insurance_type_2_num,
                CASE WHEN RV.rulefield_type != 'digit' THEN COALESCE(VV.char_value, '') END AS insurance_type_2_char

            FROM llp_payroll A
                LEFT JOIN llp_payroll_line B ON B.payroll_id = A.id
                LEFT JOIN hr_employee EMP ON EMP.id = B.employee_id
                LEFT JOIN hr_department HD ON HD.id = EMP.department_id
                LEFT JOIN (
                    SELECT *
                    FROM llp_payroll_report_config
                    WHERE type = 'income_tax_import'
                    ORDER BY id
                    LIMIT 1
                ) C ON TRUE
                LEFT JOIN llp_payroll_rule RA ON RA.id = C.taxpayer_number
                LEFT JOIN llp_payroll_rule_value VA ON VA.payroll_rule_id = RA.id AND B.id = VA.line_id
                LEFT JOIN llp_payroll_rule RLN ON RLN.id = C.last_name
                LEFT JOIN llp_payroll_rule_value VLN ON VLN.payroll_rule_id = RLN.id AND B.id = VLN.line_id
                LEFT JOIN llp_payroll_rule RFN ON RFN.id = C.first_name
                LEFT JOIN llp_payroll_rule_value VFN ON VFN.payroll_rule_id = RFN.id AND B.id = VFN.line_id
                LEFT JOIN llp_payroll_rule RB ON RB.id = C.income_7_1_1
                LEFT JOIN llp_payroll_rule_value VB ON VB.payroll_rule_id = RB.id AND B.id = VB.line_id
                LEFT JOIN llp_payroll_rule RC ON RC.id = C.income_7_1_2_7
                LEFT JOIN llp_payroll_rule_value VC ON VC.payroll_rule_id = RC.id AND B.id = VC.line_id
                LEFT JOIN llp_payroll_rule RD ON RD.id = C.income_7_1_6
                LEFT JOIN llp_payroll_rule_value VD ON VD.payroll_rule_id = RD.id AND B.id = VD.line_id
                LEFT JOIN llp_payroll_rule RE ON RE.id = C.total_income_1_2_3
                LEFT JOIN llp_payroll_rule_value VE ON VE.payroll_rule_id = RE.id AND B.id = VE.line_id
                LEFT JOIN llp_payroll_rule RF ON RF.id = C.insurance_rate
                LEFT JOIN llp_payroll_rule_value VF ON VF.payroll_rule_id = RF.id AND B.id = VF.line_id
                LEFT JOIN llp_payroll_rule RG ON RG.id = C.insurance_amount_main
                LEFT JOIN llp_payroll_rule_value VG ON VG.payroll_rule_id = RG.id AND B.id = VG.line_id
                LEFT JOIN llp_payroll_rule RH ON RH.id = C.insurance_amount_7_1_6
                LEFT JOIN llp_payroll_rule_value VH ON VH.payroll_rule_id = RH.id AND B.id = VH.line_id
                LEFT JOIN llp_payroll_rule RI ON RI.id = C.taxable_income
                LEFT JOIN llp_payroll_rule_value VI ON VI.payroll_rule_id = RI.id AND B.id = VI.line_id
                LEFT JOIN llp_payroll_rule RJ ON RJ.id = C.income_type
                LEFT JOIN llp_payroll_rule_value VJ ON VJ.payroll_rule_id = RJ.id AND B.id = VJ.line_id
                LEFT JOIN llp_payroll_rule RK ON RK.id = C.income_amount
                LEFT JOIN llp_payroll_rule_value VK ON VK.payroll_rule_id = RK.id AND B.id = VK.line_id
                LEFT JOIN llp_payroll_rule RL ON RL.id = C.total_taxable_income
                LEFT JOIN llp_payroll_rule_value VL ON VL.payroll_rule_id = RL.id AND B.id = VL.line_id
                LEFT JOIN llp_payroll_rule RM ON RM.id = C.tax_bracket
                LEFT JOIN llp_payroll_rule_value VM ON VM.payroll_rule_id = RM.id AND B.id = VM.line_id
                LEFT JOIN llp_payroll_rule RN ON RN.id = C.tax_calculated
                LEFT JOIN llp_payroll_rule_value VN ON VN.payroll_rule_id = RN.id AND B.id = VN.line_id
                LEFT JOIN llp_payroll_rule RO ON RO.id = C.months_worked
                LEFT JOIN llp_payroll_rule_value VO ON VO.payroll_rule_id = RO.id AND B.id = VO.line_id
                LEFT JOIN llp_payroll_rule RP ON RP.id = C.discount_monthly
                LEFT JOIN llp_payroll_rule_value VP ON VP.payroll_rule_id = RP.id AND B.id = VP.line_id
                LEFT JOIN llp_payroll_rule RQ ON RQ.id = C.discount_total
                LEFT JOIN llp_payroll_rule_value VQ ON VQ.payroll_rule_id = RQ.id AND B.id = VQ.line_id
                LEFT JOIN llp_payroll_rule RR ON RR.id = C.tax_after_discount_7_1_1
                LEFT JOIN llp_payroll_rule_value VR ON VR.payroll_rule_id = RR.id AND B.id = VR.line_id
                LEFT JOIN llp_payroll_rule RS ON RS.id = C.tax_7_1_6
                LEFT JOIN llp_payroll_rule_value VS ON VS.payroll_rule_id = RS.id AND B.id = VS.line_id
                LEFT JOIN llp_payroll_rule RT ON RT.id = C.total_tax_withheld
                LEFT JOIN llp_payroll_rule_value VT ON VT.payroll_rule_id = RT.id AND B.id = VT.line_id
                LEFT JOIN llp_payroll_rule RU ON RU.id = C.annual_discount_diff
                LEFT JOIN llp_payroll_rule_value VU ON VU.payroll_rule_id = RU.id AND B.id = VU.line_id
                LEFT JOIN llp_payroll_rule RV ON RV.id = C.insurance_type_2
                LEFT JOIN llp_payroll_rule_value VV ON VV.payroll_rule_id = RV.id AND B.id = VV.line_id
                LEFT JOIN llp_payroll_structure T ON T.id = A.struct_id
            WHERE A.state = 'confirmed'
            AND T.struct_type = 'salary_late'
            AND A.start_date = %s
            AND A.end_date   = %s
            AND A.company_id = %s
        """
        params = [self.start_date, self.end_date, self.company_id.id]

        if has_department:
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

        headers = [u'Хэлтэс']
        headers += [
            u'Татвар төлөгчийн дугаар',
            u'Овог',
            u'Нэр',
            u'Хуулийн 7.1.1',
            u'Хуулийн 7.1.2, 7.1.3, 7.1.4, 7.1.5, 7.1.7',
            u'Хуулийн 7.1.6',
            u'Нийт (1+2+3)',
            u'ЭМД, НДШ Хувь',
            u'ЭМД, НДШ Дүн (Хуулийн 7,1,1-5, 7,1,7)',
            u'ЭМД, НДШ Дүн (Хуулийн 7,1,6)',
            u'Хуулийн 7.1-д заасан орлогод татвар ногдуулах орлого (4-6-7)',
            u'Орлогын төрөл',
            u'Орлого',
            u'Нийт татвар ногдуулах орлого',
            u'Шатлал',
            u'Хуулийн 7.1.1, 7.1.5, 7.1.7-д заасан орлогод Ногдуулсан татвар',
            u'Орлого хүлээн авсан сарын тоо /ажилласан сар/',
            u'Хуулийн 23.1-т заасан хөнгөлөлт сард ногдох',
            u'Хуулийн 23.1-т заасан хөнгөлөлт нийт',
            u'7.1.1 -д заасан Хөнгөлөлтийн дараах татварын дүн',
            u'Хуулийн 7.1.6-д заасан орлогод ногдуулсан дүн',
            u'Нийт суутгуулсан албан татварын дүн',
            u'Жилийн ХХОАТ-ын хөнгөлөлтийн зөрүү',
            u'Даатгалын төрөл',
        ]

        for col_idx, header in enumerate(headers):
            sheet.write(0, col_idx, header, header_fmt)
        sheet.set_row(0, 40)

        dept_offset = 1
        field_count = 24

        for row_idx, row in enumerate(rows, start=1):
            sheet.write(row_idx, 0, row[0] or '', cell_fmt)

            for i in range(field_count):
                num_val = row[dept_offset + i * 2]
                char_val = row[dept_offset + i * 2 + 1]
                col_idx = dept_offset + i
                if num_val is not None:
                    sheet.write_number(row_idx, col_idx, float(num_val), num_fmt)
                else:
                    sheet.write(row_idx, col_idx, char_val or '', cell_fmt)

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

        dept_col = 0
        start_row = 1
        current_dept = rows[0][0]

        def write_dept_block(s_row, e_row, dept_value):
            dept_value = dept_value or ''
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
        file_name = u'ХХОАТ-ын импорт хийх загвар'
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