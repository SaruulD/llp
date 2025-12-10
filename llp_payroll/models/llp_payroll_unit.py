# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore

class LLPPayrollUnit(models.Model):
	_name = 'llp.payroll.unit'
	_inherit = ['mail.thread']
	_description = "LLP payroll unit"
	_order = "create_date desc"


	name = fields.Char(string="Name",tracking=True)
	code = fields.Char(string="Code",tracking=True)
	department_ids = fields.Many2many('hr.department', string="Departments", tracking=True)
	journal_id = fields.Many2one('account.journal', string="Journal", tracking=True)
	line_ids = fields.One2many('llp.payroll.unit.line','unit_id',string="Unit lines",tracking=True)
	active = fields.Boolean(string="Active",default=True)

	@api.model
	def create(self, vals):
		result = super(LLPPayrollUnit, self).create(vals)
		return result

	def write(self, vals):
		result = super(LLPPayrollUnit, self).write(vals)
		return result
	
class LLPPayrollUnitLine(models.Model):
	_name = 'llp.payroll.unit.line'

	unit_id = fields.Many2one('llp.payroll.unit',string="Unit")
	rule_id = fields.Many2one('llp.payroll.rule',string="Rule")

	# TODO: duusgaad comment ustgah
	# changed note -> transaction_value
	transaction_value = fields.Text(string="Transaction value")
	debit_account_id = fields.Many2one('account.account',string="Debit account")
	credit_account_id = fields.Many2one('account.account',string="Credit account")