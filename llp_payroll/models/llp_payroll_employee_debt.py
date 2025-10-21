# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from datetime import date,datetime
from dateutil.relativedelta import relativedelta # type: ignore

class LLPPayrollEmployeeDebt(models.Model):
	_name ='llp.payroll.employee.debt'
	_inherit = ['mail.thread']
	_description = "LLP payroll debt"
	_order = "create_date desc"

	name = fields.Char(related='code')
	code = fields.Char(string="Code")
	month = fields.Date(string="Month",required=True, tracking=True)
	department_ids = fields.Many2many('hr.department', string="Departments", tracking=True)
	dynamic_workflow_id = fields.Many2one('dynamic.workflow', string="Dynamic workflow")
	struct_type = fields.Selection([('salary_advance','Salary advance'),('salary_late','Salary late')],string="Type")
	state = fields.Selection([
		('draft', 'Draft'), # Ноорог
		('done', 'Done'), # Батлагдсан
		('closed', 'Closed'), # Хаагдсан
	], string="State", default='draft', tracking=True)
	line_ids = fields.One2many('llp.payroll.employee.debt.line','debt_id',string="Lines")

	@api.model
	def create(self, vals):
		seq_code = 'llp.payroll.employee.debt.seq'
		if not self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1):
			self.env['ir.sequence'].sudo().create({
				'name': 'LLP Debt Sequence',
				'code': seq_code,
            	'prefix': 'Debt/%(year)s/',
				'padding': 4,
				'number_next': 1,
				'number_increment': 1,
			})

		vals['code'] = self.env['ir.sequence'].next_by_code(seq_code) or '/'

		result = super(LLPPayrollEmployeeDebt, self).create(vals)
		return result

	
	def write(self, vals):
		result = super(LLPPayrollEmployeeDebt, self).write(vals)
		return result

	def unlink(self):
		for rec in self:
			if rec.state != 'draft':
				raise UserError(_("Зөвхөн ноорог төлөвт байгаа бичлэгүүдийг устгаж болно."))

		return super(LLPPayrollEmployeeDebt, self).unlink()
	

	def action_confirm(self):
		# TODO: Ноорог цалин дээрх дүн update хийгдэнэ. 
		self.write({'state':'done'})

	def action_return(self):
		# TODO: Батлагдсан Авлага суутгах дүн Ноорогоос бусад төлвийн цалинд ашиглагдсан бол “Ноорог” болгох боломжгүй. Анхааруулга өгнө.
		self.write({'state':'draft'})


class LLPPayrollEmployeeDebtLine(models.Model):
	_name ='llp.payroll.employee.debt.line'
	_inherit = ['mail.thread']
	_description = "LLP payroll debt line"
	_order = "create_date desc"

	employee_id = fields.Many2one(
		'hr.employee',
		string="Employee",
		required=True,
		tracking=True
	)
	department_id = fields.Many2one('hr.department', string="Department", related='employee_id.department_id', store=True, readonly=True)
	debt_id = fields.Many2one('llp.payroll.employee.debt', string="Debt")
	currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id
    )
	# TODO: нийт авлагын дүн оруулах 1202, 1206-тай данс
	total_debt = fields.Monetary(string="Total debt", tracking=True, currency_field='currency_id')
	balance = fields.Monetary(string="Balance", readonly=True, 
		compute="_compute_balance",
		store=True)
	withholding_amount = fields.Monetary(
		string="Withholding amount",
		tracking=True,
		currency_field='currency_id',
	)
	line_details_ids = fields.One2many(
		'llp.payroll.employee.debt.line.details',
		'line_id',
		string="Line details",
	)

	@api.depends('total_debt', 'balance')
	def _compute_balance(self):
		for rec in self:
			rec.balance = rec.total_debt - rec.withholding_amount



class LLPPayrollEmployeeDebtLineDetails(models.Model):
	_name ='llp.payroll.employee.debt.line.details'
	_inherit = ['mail.thread']
	_description = "LLP payroll debt line details"
	_order = "create_date desc"

	line_id = fields.Many2one('llp.payroll.employee.debt.line', string="Line")
	date = fields.Date(string="Date", readonly=True)
	transaction_value = fields.Text(string="Transaction value", readonly=True)
	amount = fields.Monetary(string="Amount", readonly=True, currency_field='currency_id')
	currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id
    )