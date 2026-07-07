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
	company_id = fields.Many2one('res.company', string="Company",default=lambda self: self.env.company,)
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

	def action_get_data(self):
		DebtLine = self.env['llp.payroll.employee.debt.line'].sudo()
		Detail = self.env['llp.payroll.employee.debt.line.details'].sudo()

		for debt in self:
			if not debt.department_ids:
				raise UserError(_("Please select departments."))

			emp_domain = [
				('active', '=', True),
				('department_id', 'in', debt.department_ids.ids),
				('work_contact_id', '!=', False),
			]
			if debt.company_id:
				emp_domain.append(('company_id', 'in', debt.company_id.ids))

			employees = self.env['hr.employee'].sudo().search(emp_domain)
			if not employees:
				continue

			emp_partner = {e.id: e.work_contact_id.id for e in employees if e.work_contact_id}
			partner_to_emp = {}
			for emp_id, partner_id in emp_partner.items():
				partner_to_emp.setdefault(partner_id, []).append(emp_id)

			partners = self.env['res.partner'].browse(list(partner_to_emp.keys()))
			if not partners:
				continue

			line_by_emp = {l.employee_id.id: l for l in debt.line_ids if l.employee_id}

			debt.line_ids.mapped('line_details_ids').unlink()

			aml_domain = [
				('partner_id', 'in', partners.ids),
				('account_id.account_type', 'in', ['asset_receivable', 'asset_current']),
				('move_id.state', '=', 'posted'),
				('amount_residual', '!=', 0),
			]
			if debt.month:
				aml_domain.append(('date', '<=', debt.month))

			amls = self.env['account.move.line'].sudo().search(
				aml_domain,
				order='partner_id, date asc, id asc'
			)
			if not amls:
				continue

			aml_partner_ids = set(amls.mapped('partner_id').ids)
			for p_id in aml_partner_ids:
				for emp_id in partner_to_emp.get(p_id, []):
					if emp_id not in line_by_emp:
						line_by_emp[emp_id] = DebtLine.create({
							'debt_id': debt.id,
							'employee_id': emp_id,
						})

			create_vals = []
			for aml in amls:
				p_id = aml.partner_id.id
				for emp_id in partner_to_emp.get(p_id, []):
					line = line_by_emp.get(emp_id)
					if not line:
						continue

					create_vals.append({
						'line_id': line.id,
						'date': aml.date,
						'transaction_value': aml.name or aml.move_name or '',
						'amount': aml.amount_residual,
					})

			if create_vals:
				Detail.create(create_vals)

		return True

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
	total_debt = fields.Monetary(string="Total debt", tracking=True, currency_field='currency_id', compute="_compute_total_debt", store=True)
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

	@api.depends('line_details_ids.amount')
	def _compute_total_debt(self):
		for line in self:
			line.total_debt = sum(line.line_details_ids.mapped('amount'))

	@api.depends('total_debt', 'withholding_amount')
	def _compute_balance(self):
		for rec in self:
			rec.balance = (rec.total_debt or 0.0) - (rec.withholding_amount or 0.0)



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