# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ #type: ignore
from odoo.exceptions import UserError #type: ignore

class LLPPayrollStructure(models.Model):
	_name = 'llp.payroll.structure'
	_inherit = ['mail.thread']
	_description = "LLP payroll structure"
	_order = "create_date desc"


	name = fields.Char(string="Name",tracking=True)
	struct_type = fields.Selection([('salary_advance','Salary advance'),
									('salary_late','Salary late')],string="Structure type",tracking=True)
	line_ids = fields.One2many('llp.payroll.structure.line','struct_id',string='Rule lines')
	state = fields.Selection([('draft','Draft'),('done','Done')],string='State',default='draft',tracking=True)

	def action_confirm(self):
		
		rules = []
		for line in self.line_ids:
			if line.rule_id.id not in rules:
				rules.append(line.rule_id.id)
			else:
				raise UserError((u'%s дүрмийн мэдээлэл давхардаж байна.'%(line.rule_id.name)))
		self.write({'state':'done'})

	def action_draft(self):
		self.write({'state':'draft'})

class LLPPayrollStructureLine(models.Model):
	_name = 'llp.payroll.structure.line'
	_description = "LLP payroll structure line"
	_order = "exp_sequence asc"

	struct_id = fields.Many2one('llp.payroll.structure',string="Payroll structure")
	rule_id = fields.Many2one('llp.payroll.rule',string="Payroll rule",ondelete='restrict')
	rule_code = fields.Char(related='rule_id.code', string="Rule Code", readonly=True)
	sequence = fields.Integer(string="Sequence")
	exp_sequence = fields.Integer(string="Expression Sequence")

