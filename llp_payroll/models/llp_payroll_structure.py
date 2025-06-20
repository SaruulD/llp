# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class LLPPayrollStructure(models.Model):
	_name = 'llp.payroll.structure'
	_inherit = ['mail.thread']
	_description = "LLP payroll structure"
	_order = "create_date desc"


	name = fields.Char(string="Name",track_visibility='onchange')
	struct_type = fields.Selection([('bonus','Bonus'),
									('salary_advance','Salary advance'),
									('salary_late','Salary late')],string="Structure type",track_visibility='onchange')
	line_ids = fields.One2many('llp.payroll.structure.line','struct_id',string='Rule lines')
	state = fields.Selection([('draft','Draft'),('done','Done')],string='State',default='draft',track_visibility='onchange')

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
	_order = "exp_sequence asc"

	struct_id = fields.Many2one('llp.payroll.structure',string="Payroll structure")
	rule_id = fields.Many2one('llp.payroll.rule',string="Payroll rule",ondelete='restrict')
	sequence = fields.Integer(string="Sequence")
	exp_sequence = fields.Integer(string="Expression Sequence")

