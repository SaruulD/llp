# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression

class LLPPayrollRule(models.Model):
	_name = 'llp.payroll.rule'
	_inherit = ['mail.thread']
	_description = "LLP payroll rule"
	_order = "create_date desc"


	name = fields.Char(string="Name",track_visibility='onchange')
	parent_id = fields.Many2one('llp.payroll.rule',string="Parent rule",track_visibility='onchange')
	code = fields.Char(string="Code",track_visibility='onchange')
	description = fields.Text(string="Description",track_visibility='onchange')	
	rule_type = fields.Selection([('percent','Percent'),('regular','Regular'),('code','Code')],string="Rule type",track_visibility='onchange',default='regular')
	value_type = fields.Selection([('get_value','Get value'),('expression','Expression')],string="Value type",track_visibility='onchange',default='get_value')
	python_code = fields.Text(string="Python code" ,track_visibility='onchange')
	percent = fields.Float(string="Percent" ,track_visibility='onchange')
	regular_number = fields.Float(string="Regular number" ,track_visibility='onchange')
	active = fields.Boolean(string="Active",default=True)
	show_in_payroll = fields.Boolean(string="Show in payroll",default=True)
	decimal_point = fields.Integer(string='Decimal point')
	is_vacation_salary = fields.Boolean(string="Is vacation salary",default=False)
	is_vacation_time = fields.Boolean(string="Is vacation time",default=False)
	is_show_sum = fields.Boolean(string="Is show sum",default=False)
	ruleview_type = fields.Selection([('view','View'),('edit','Edit')],string="Rule view type",default="view",track_visibility='onchange')
	rulefield_type = fields.Selection([('digit','Digit'),('sign','Sign'),('from_previous_month','Get from previous month')], string="Rule field type", default="digit",track_visibility='onchange')
	history_ids = fields.One2many('llp.payroll.rule.history','rule_id',string="Rule histories")
	transaction_type = fields.Selection([('salary_advance','Salary advance'),
											('salary_late','Salary late'),
										], string="Transaction type")
	
	_sql_constraints = [
		('code_uniq', 'unique(code)',
		("There is already a rule defined on this model\n"
		"You cannot define another: please edit the existing one or change this one."))
	]


	
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

	
	def action_done(self):
		translations = self.env['ir.translation'].search([('lang', '=', 'mn_MN')])
		print(f"Found {len(translations)} lines")


		self.write({'state':'confirmed'})
		for his in self.history_ids:
			if not his.end_date:
				his.write({'end_date':fields.Date.context_today(self)})
		if self.python_code:
			# month_id = self.env['account.period'].sudo().search([('date_start','<=',fields.Date.context_today(self)),('date_stop','>=',fields.Date.context_today(self))])
			self.env['llp.payroll.rule.history'].create({
			'rule_id':self.id,
			# 'month_id':month_id.id,
			'start_date':fields.Date.context_today(self),
			'note':self.python_code,
			})

	
	def action_draft(self):
		self.write({'state':'draft'})
		

class LLPPayrollRuleHistory(models.Model):
	_name = 'llp.payroll.rule.history'
	_order = "create_date desc"
	
	# month_id = fields.Many2one('account.period',string="Month")
	start_date = fields.Date(string="Start date")
	end_date = fields.Date(string="end date")
	note = fields.Text(string="Note")	
	rule_id = fields.Many2one('llp.payroll.rule',string="Rule")
