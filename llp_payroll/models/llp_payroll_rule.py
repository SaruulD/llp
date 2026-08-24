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
	rule_type = fields.Selection([('regular','Regular'),('code','Code')],string="Rule type",tracking=True,default='regular')
	python_code = fields.Text(string="Python code" ,tracking=True)
	percent = fields.Float(string="Percent" ,tracking=True)
	regular_number = fields.Float(string="Regular number" ,tracking=True)
	active = fields.Boolean(string="Active",default=True)
	show_in_payroll = fields.Boolean(string="Show in payroll",default=True)
	show_in_report = fields.Boolean(string="Show in report",default=True)
	is_net_amount = fields.Boolean(string="Is net amount",default=False, help='Банкны тайланд хэвлэгдэх дүн.')
	decimal_point = fields.Integer(string='Decimal point')
	is_vacation_salary = fields.Boolean(string="Is vacation salary",default=False)
	is_vacation_time = fields.Boolean(string="Is vacation time",default=False)
	is_show_sum = fields.Boolean(string="Is show sum",default=False)
	ruleview_type = fields.Selection([('view','View'),('edit','Edit')],string="Rule view type",default="view",tracking=True)
	rulefield_type = fields.Selection([('digit','Digit'),('sign','Sign'),('from_previous_payroll','Get from previous payroll')], string="Rule field type", default="digit",tracking=True)
	history_ids = fields.One2many('llp.payroll.rule.history','rule_id',string="Rule histories")
	transaction_type = fields.Selection([('salary_advance','Salary advance'),
											('salary_late','Salary late'),
											('by_partner','By partner'),
										], string="Transaction type")
	need_highlight = fields.Boolean("Тодруулах шаардлагатай")
	
	send_mail = fields.Boolean(string='Send E-Mail', default=False)

	company_id = fields.Many2one('res.company', string="Company",default=lambda self: self.env.company,)
	object_type = fields.Selection([('attendance','Attendance'),
								 ('contract','Contract'),
								 ('vacation','Vacation'),
								 ('debt','Debt'),
								 ('kpi','Kpi'),
								 ('employee','Employee'),
								 ('part_time_work_additional_salary','Contract - Хавсран ажлын нэмэгдэл цалин'),
								 ('part_time_work_additional_salary_percent','Contract - Хавсран ажлын нэмэгдэл цалингийн хувь'),
								 ],string="Object type",tracking=True)	
	structure_line_ids = fields.One2many(
		'llp.payroll.structure.line', 'rule_id',
		string="Structure lines", readonly=True,
	)

	structure_ids = fields.Many2many(
		'llp.payroll.structure',
		string="Ашиглагдаж буй бүтцүүд",
		compute='_compute_structure_ids',
		store=True,
	)

	@api.depends('structure_line_ids.struct_id')
	def _compute_structure_ids(self):
		for rec in self:
			rec.structure_ids = rec.structure_line_ids.mapped('struct_id')
	
	_sql_constraints = [
		('code_uniq', 'unique(code)',
		("There is already a rule defined on this model\n"
		"You cannot define another: please edit the existing one or change this one."))
	]
	def _get_object_type_base_map(self):
			"""object_type-ийн утга бүрийг action_computebyQUERY() доторх аль
			үндсэн ангилалд (contract/vacation/debt/attendance/kpi/employee)
			харгалзахыг тодорхойлно. llp_payroll модуль ЗӨВХӨН эдгээр 6 үндсэн
			ангиллыг л мэднэ.
	
			Өөр модуль (жишээ нь ug_regulation, llp_hr_penalty) шинэ object_type
			утга нэмэх бол, энэ функцийг super()-оор дуудаад, өөрийн шинэ
			утгаа аль үндсэн ангилалд харьяалагдахыг нэмж өгнө. Ингэснээр
			llp_payroll модуль тэдгээр модулиудаас хамааралгүй, бие даан
			ажиллах боломжтой хэвээр үлдэнэ."""
			return {
				'contract': 'contract',
				'part_time_work_additional_salary': 'contract',
				'part_time_work_additional_salary_percent': 'contract',
				'vacation': 'vacation',
				'debt': 'debt',
				'attendance': 'attendance',
				'kpi': 'kpi',
				'employee': 'employee',
		}
 
	def _get_python_code_templates(self):
		"""object_type-ийн "shortcut" утгуудын ард нуугдах бэлэн Python code.
		Өөр модуль (ug_regulation, llp_hr_penalty) энэ функцийг super()-оор
		дуудаад, өөрийн шинэ object_type-той холбоотой бэлэн кодоо нэмж
		өгнө."""
		return {
			'part_time_work_additional_salary': (
"""result = 0
if object:
    if object.part_time_work_start_date or object.part_time_work_end_date:
        if object.part_time_work_start_date >= payroll_start_date and object.part_time_work_start_date <= payroll_end_date or payroll_start_date <= object.part_time_work_end_date and payroll_end_date >= object.part_time_work_end_date:
            result = object.part_time_work_additional_salary"""
			),
			'part_time_work_additional_salary_percent': (
"""result = 0
if object:
    if object.part_time_work_start_date or object.part_time_work_end_date:
        if object.part_time_work_start_date >= payroll_start_date and object.part_time_work_start_date <= payroll_end_date or payroll_start_date <= object.part_time_work_end_date and payroll_end_date >= object.part_time_work_end_date:
            result = object.part_time_work_additional_salary_percent"""
			),
		}
	
	@api.onchange('object_type')
	def _onchange_object_type_python_code_shortcut(self):
		for rec in self:
			templates = rec._get_python_code_templates()
			if rec.object_type in templates:
				rec.python_code = templates[rec.object_type]
			elif rec.python_code in templates.values():
				# өмнө нь shortcut-аар автоматаар бичигдсэн байсан кодыг,
				# өөр object_type рүү шилжихэд цэвэрлэнэ
				rec.python_code = ''

	
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
	
	def copy(self, default=None):
		default = default or {}
		default.update({
			'code': False,
		})
		new_rule = super().copy(default)
		return new_rule
	
	def write(self, vals):
		history_model = self.env['llp.payroll.rule.history']
		fields_to_watch = [
			'name', 'code', 'description', 'rule_type', 'python_code',
			'percent', 'regular_number', 'decimal_point', 'transaction_type',
			'object_type', 'is_vacation_salary', 'is_vacation_time', 'is_show_sum'
		]
		today = fields.Date.context_today(self)
		histories = []
		for rec in self:
			changes = []
			for f in fields_to_watch:
				if f in vals:
					old = rec[f]
					new = vals.get(f)

					if hasattr(old, 'id'):
						old_disp = old.id
					else:
						old_disp = old

					if hasattr(new, 'id'):
						new_disp = new.id
					else:
						new_disp = new

					if old_disp != new_disp:
						changes.append("%s: %r -> %r" % (f, old_disp, new_disp))
			if changes:
				histories.append({
					'rule_id': rec.id,
					'start_date': today,
					'note': '; '.join(changes)
				})
		if histories:
			for history in self.history_ids:
				if not history.end_date:
					history.write({'end_date':today})
					
			history_model.create(histories)
		return super(LLPPayrollRule, self).write(vals)

class LLPPayrollRuleHistory(models.Model):
	_name = 'llp.payroll.rule.history'
	_description = "LLP payroll rule history"
	_order = "create_date desc"
	
	start_date = fields.Date(string="Start date")
	end_date = fields.Date(string="end date")
	note = fields.Text(string="Note")	
	rule_id = fields.Many2one('llp.payroll.rule',string="Rule")
