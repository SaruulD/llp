# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from odoo.osv import expression # type: ignore

class LLPPayrollRule(models.Model):
	_name = 'llp.payroll.rule'
	_inherit = ['mail.thread']
	_description = "LLP payroll rule"
	_order = "create_date desc"


	name = fields.Char(string="Name",tracking=True)
	parent_id = fields.Many2one('llp.payroll.rule',string="Parent rule",tracking=True)
	code = fields.Char(string="Code",tracking=True)
	description = fields.Text(string="Description",tracking=True)	
	rule_type = fields.Selection([('percent','Percent'),('regular','Regular'),('code','Code')],string="Rule type",tracking=True,default='regular')
	value_type = fields.Selection([('get_value','Get value'),('expression','Expression')],string="Value type",tracking=True,default='get_value')
	python_code = fields.Text(string="Python code" ,tracking=True)
	percent = fields.Float(string="Percent" ,tracking=True)
	regular_number = fields.Float(string="Regular number" ,tracking=True)
	active = fields.Boolean(string="Active",default=True)
	show_in_payroll = fields.Boolean(string="Show in payroll",default=True)
	decimal_point = fields.Integer(string='Decimal point')
	is_vacation_salary = fields.Boolean(string="Is vacation salary",default=False)
	is_vacation_time = fields.Boolean(string="Is vacation time",default=False)
	is_show_sum = fields.Boolean(string="Is show sum",default=False)
	ruleview_type = fields.Selection([('view','View'),('edit','Edit')],string="Rule view type",default="view",tracking=True)
	rulefield_type = fields.Selection([('digit','Digit'),('sign','Sign'),('from_previous_month','Get from previous month')], string="Rule field type", default="digit",tracking=True)
	history_ids = fields.One2many('llp.payroll.rule.history','rule_id',string="Rule histories")
	transaction_type = fields.Selection([('salary_advance','Salary advance'),
											('salary_late','Salary late'),
										], string="Transaction type")
	object_type = fields.Selection([('attendance','Attendance'),
								 ('contract','Contract'),
								 ('vacation','Vacation'),
								 ('debt','Debt'),
								 ('kpi','Kpi')],string="Object type",tracking=True)

	# TODO: transaction_type doc-oos harah
	# is_rule_type_percent = fields.Boolean(compute='_compute_same_currency')
	
	
	_sql_constraints = [
		('code_uniq', 'unique(code)',
		("There is already a rule defined on this model\n"
		"You cannot define another: please edit the existing one or change this one."))
	]


	# @api.depends('rule_type')
	# def _compute_same_currency(self):
	# 	for record in self:
	# 		record.is_rule_type_percent = record.rule_type == 'percent' 


	
	@api.depends('name', 'code')
	def name_get(self):
		result = []
		for acc in self:
			name = acc.name
			if acc.code:
				name += ' [%s]'%(acc.code)
			result.append((acc.id, name))
		return result

	@api.model
	def name_search(self, name, args=None, operator='ilike', limit=100):
		args = args or []
		domain = []
		if name:
			domain = ['|',('code', '=ilike', '%' + name),('name', operator, name)]
			if operator in expression.NEGATIVE_TERM_OPERATORS:
				domain = ['&'] + domain
		departs = self.search(domain + args, limit=limit)
		return departs.name_get()

class LLPPayrollRuleHistory(models.Model):
	_name = 'llp.payroll.rule.history'
	_description = "LLP payroll rule history"
	_order = "create_date desc"
	
	start_date = fields.Date(string="Start date")
	end_date = fields.Date(string="end date")
	note = fields.Text(string="Note")	
	rule_id = fields.Many2one('llp.payroll.rule',string="Rule")
