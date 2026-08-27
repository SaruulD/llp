# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from odoo.osv import expression # type: ignore

class LLPPayrollReportConfig(models.Model):
    _name = 'llp.payroll.report.config'
    _inherit = ['mail.thread']
    _description = "LLP payroll report config"
    _order = "create_date desc"


    company_id = fields.Many2one('res.company', string="Company",default=lambda self: self.env.company,)
    type = fields.Selection([
        # ('insurance_tax_report','Insurance Tax Report'),
        # ('insurance_report','Insurance Report'),
        ('insurance_tax_import','Insurance Tax Import'),
        # ('income_tax_report','Income Tax Report'),
        ('income_tax_import','Income Tax Import')],string="Type",tracking=True,default='insurance_tax_import')
    
    civil_number = fields.Many2one('llp.payroll.rule', string='Иргэний дугаар', tracking=True)
    register_number = fields.Many2one('llp.payroll.rule', string='Регистрийн дугаар', tracking=True)
    family_name = fields.Many2one('llp.payroll.rule', string='Ургийн овог', tracking=True)
    last_name = fields.Many2one('llp.payroll.rule', string='Овог', tracking=True)
    first_name = fields.Many2one('llp.payroll.rule', string='Нэр', tracking=True)
    insurance_type = fields.Many2one('llp.payroll.rule', string='Даатгуулагчийн төрөл', tracking=True)
    citizenship = fields.Many2one('llp.payroll.rule', string='Иргэншил', tracking=True)
    wages_and_equivalent_income = fields.Many2one('llp.payroll.rule',string='Хөдөлмөрийн хөлс түүнтэй адилтгах орлого', tracking=True)
    base_and_additional_salary = fields.Many2one('llp.payroll.rule', string='Үндсэн ба нэмэгдэл цалин', tracking=True)
    bonus_salary = fields.Many2one('llp.payroll.rule', string='Шагналт цалин', tracking=True)
    other_additional_salary = fields.Many2one('llp.payroll.rule', string='Бусад нэмэгдэл цалин', tracking=True)
    food_transportation_cost = fields.Many2one('llp.payroll.rule', string='Хоол унааны хөлс', tracking=True)
    firewood_discount = fields.Many2one('llp.payroll.rule', string='Түлээ нүүрсний үнийн хөнгөлөлт', tracking=True)
    career_classification = fields.Many2one('llp.payroll.rule', string='Ажил мэргэжлийн ангилал', tracking=True)
    cellphone = fields.Many2one('llp.payroll.rule', string='Харилцах утасны дугаар', tracking=True)
    email = fields.Many2one('llp.payroll.rule', string='Цахим шуудангийн хаяг', tracking=True)

    job = fields.Many2one('llp.payroll.rule', string='Албан тушаал', tracking=True)
    insurance_tax_employer = fields.Many2one('llp.payroll.rule', string='Нийгмийн даатгалын санд төлөх шимтгэл /төгрөгөөр/ - Ажил олгогч', tracking=True)
    insurance_tax_employee = fields.Many2one('llp.payroll.rule', string='Нийгмийн даатгалын санд төлөх шимтгэл /төгрөгөөр/ - Даатгуулагч', tracking=True)
    is_limit_max = fields.Many2one('llp.payroll.rule', string='Дээд хэмжээ хязгаарлах эсэх', tracking=True)
    tax_payer_number = fields.Many2one('llp.payroll.rule', string='Татвар төлөгчийн дугаар', tracking=True)

    taxpayer_number = fields.Many2one('llp.payroll.rule', string='Татвар төлөгчийн дугаар', tracking=True)
    income_7_1_1 = fields.Many2one('llp.payroll.rule', string='Хуулийн 7.1.1', tracking=True)
    income_7_1_2_7 = fields.Many2one('llp.payroll.rule', string='Хуулийн 7.1.2, 7.1.3, 7.1.4, 7.1.5, 7.1.7', tracking=True)
    income_7_1_6 = fields.Many2one('llp.payroll.rule', string='Хуулийн 7.1.6', tracking=True)
    total_income_1_2_3 = fields.Many2one('llp.payroll.rule', string='Нийт (1+2+3)', tracking=True)
    insurance_rate = fields.Many2one('llp.payroll.rule', string='ЭМД, НДШ Хувь', tracking=True)
    insurance_amount_main = fields.Many2one('llp.payroll.rule', string='ЭМД, НДШ Дүн (Хуулийн 7,1,1-5, 7,1,7)', tracking=True)
    insurance_amount_7_1_6 = fields.Many2one('llp.payroll.rule', string='ЭМД, НДШ Дүн (Хуулийн 7,1,6)', tracking=True)
    taxable_income = fields.Many2one('llp.payroll.rule', string='Хуулийн 7.1-д заасан орлогод татвар ногдуулах орлого (4-6-7)', tracking=True)
    income_type = fields.Many2one('llp.payroll.rule', string='Орлогын төрөл', tracking=True)
    income_amount = fields.Many2one('llp.payroll.rule', string='Орлого', tracking=True)
    total_taxable_income = fields.Many2one('llp.payroll.rule', string='Нийт татвар ногдуулах орлого', tracking=True)
    tax_bracket = fields.Many2one('llp.payroll.rule', string='Шатлал', tracking=True)
    tax_calculated = fields.Many2one('llp.payroll.rule', string='Хуулийн 7.1.1, 7.1.5, 7.1.7-д заасан орлогод Ногдуулсан татвар', tracking=True)
    months_worked = fields.Many2one('llp.payroll.rule', string='Орлого хүлээн авсан сарын тоо /ажилласан сар/', tracking=True)
    discount_monthly = fields.Many2one('llp.payroll.rule', string='Хуулийн 23.1-т заасан хөнгөлөлт сард ногдох', tracking=True)
    discount_total = fields.Many2one('llp.payroll.rule', string='Хуулийн 23.1-т заасан хөнгөлөлт нийт', tracking=True)
    tax_after_discount_7_1_1 = fields.Many2one('llp.payroll.rule', string='7.1.1 -д заасан Хөнгөлөлтийн дараах татварын дүн', tracking=True)
    tax_7_1_6 = fields.Many2one('llp.payroll.rule', string='Хуулийн 7.1.6-д заасан орлогод ногдуулсан дүн', tracking=True)
    total_tax_withheld = fields.Many2one('llp.payroll.rule', string='Нийт суутгуулсан албан татварын дүн', tracking=True)
    annual_discount_diff = fields.Many2one('llp.payroll.rule', string='Жилийн ХХОАТ-ын хөнгөлөлтийн зөрүү', tracking=True)
    insurance_type_2 = fields.Many2one('llp.payroll.rule', string='Даатгалын төрөл', tracking=True)
    name = fields.Char(
        string="Name",
        compute='_compute_name',
        store=True,
    )

    @api.depends('type')
    def _compute_name(self):
        selection_dict = dict(self._fields['type'].selection)
        for rec in self:
            rec.name = selection_dict.get(rec.type) or ''

    _sql_constraints = [
        ('unique_type_company', 'unique(type, company_id)', 'Type must be unique per company.'),
    ]