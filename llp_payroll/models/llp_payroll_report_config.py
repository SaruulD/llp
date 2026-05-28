# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from odoo.osv import expression # type: ignore

class LLPPayrollReportConfig(models.Model):
    _name = 'llp.payroll.report.config'
    _inherit = ['mail.thread']
    _description = "LLP payroll report config"
    _order = "create_date desc"


    company_id = fields.Many2one('res.company',string="Company",tracking=True,default=lambda self: self.env.company)
    type = fields.Selection([
        ('insurance_tax_report','Insurance Tax Report'),
        ('insurance_report','Insurance Report'),
        ('insurance_tax_import','Insurance Tax Import'),
        ('income_tax_report','Income Tax Report'),
        ('income_tax_import','Income Tax Import')],string="Type",tracking=True,default='insurance_tax_report')
    
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

    _sql_constraints = [
        ('unique_type_company', 'unique(type, company_id)', 'Type must be unique per company.'),
    ]