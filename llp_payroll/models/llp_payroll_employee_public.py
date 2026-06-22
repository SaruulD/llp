from odoo import api, fields, models, tools


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"


    last_vacation_salary_date = fields.Date(related='employee_id.last_vacation_salary_date')
    next_vacation_salary_date = fields.Date(related='employee_id.next_vacation_salary_date')
