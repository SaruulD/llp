# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from datetime import date,datetime
from dateutil.relativedelta import relativedelta # type: ignore

class HrEmployee(models.Model):
	_inherit = 'hr.employee'

	last_vacation_salary_date = fields.Date(
		string="Last Vacation Salary Date", 
		tracking=True
	)
	next_vacation_salary_date = fields.Date(
		string="Next Vacation Salary Date",
		compute="_compute_next_vacation_salary_date",
		store=True,
		tracking=True
	)

	@api.depends('last_vacation_salary_date')
	def _compute_next_vacation_salary_date(self):
		for rec in self:
			if rec.last_vacation_salary_date:
				rec.next_vacation_salary_date = rec.last_vacation_salary_date + relativedelta(months=11)
			else:
				rec.next_vacation_salary_date = False



class LLPPayrollEmployeeVacation(models.Model):
	_name ='llp.payroll.employee.vacation'
	_inherit = ['mail.thread']
	_description = "LLP payroll vacation"
	_order = "create_date desc"

	name = fields.Char(related='code')
	code = fields.Char(string="Code")
	# TODO month => date (change name)
	month = fields.Date(string="Month",required=True, tracking=True)
	department_ids = fields.Many2many('hr.department', string="Departments", tracking=True)
	dynamic_workflow_id = fields.Many2one('dynamic.workflow', string="Dynamic workflow")
	struct_type = fields.Selection([('salary_advance','Salary advance'),('salary_late','Salary late')],string="Type")
	state = fields.Selection([
		('draft', 'Draft'), # Ноорог
		('pending', 'Pending Approval'), # Зөвшөөрөл хүлээж буй
		('done', 'Done'), # Батлагдсан
	], string="State", default='draft', tracking=True)
	line_ids = fields.One2many('llp.payroll.employee.vacation.line','vacation_id',string="Lines")
	history_ids = fields.One2many('request.history','payroll_vacation_id',string="State History")

	@api.model
	def create(self, vals):
		seq_code = 'llp.payroll.employee.vacation.seq'
		if not self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1):
			self.env['ir.sequence'].sudo().create({
				'name': 'LLP Vacation Sequence',
				'code': seq_code,
            	'prefix': 'SV/%(year)s/',
				'padding': 4,
				'number_next': 1,
				'number_increment': 1,
			})

		vals['code'] = self.env['ir.sequence'].next_by_code(seq_code) or '/'

		result = super(LLPPayrollEmployeeVacation, self).create(vals)
		return result

	
	def write(self, vals):
		result = super(LLPPayrollEmployeeVacation, self).write(vals)
		return result

	def unlink(self):
		for rec in self:
			if rec.state != 'draft':
				raise UserError(_("Зөвхөн ноорог төлөвт байгаа бичлэгүүдийг устгаж болно."))

		return super(LLPPayrollEmployeeVacation, self).unlink()
	

	def action_send(self):
		self.action_check_lines()
		self.write({'state':'pending'})
		self.create_history('pending')

	def action_confirm(self):
		self.write({'state':'done'})
		self.create_history('done')

	def action_return(self):
		# TODO: Үүсгэсэн хэрэглэгчид мэйл явуулах
		# shaltgaan oruulah
		self.write({'state':'draft'})
		self.create_history('draft')
	

	def create_history(self,state, note = ""):
		history_obj = self.env['request.history']
		history_obj.create({'user_id':self._uid,
									'date':fields.Date.context_today(self),
									'type':state,
									'payroll_vacation_id':self.id,
									'comment': note
									})


	def action_get_data(self):
		for vac in self:
			for department_id in vac.department_ids:
				employees = self.env['hr.employee'].sudo().search([('department_id','=',department_id.id),('active','=',True),('next_vacation_salary_date','<=',vac.month)])

				employee_months = {}
				vac_lines = {}
				for line in vac.line_ids:

					if line.employee_id.id not in vac_lines:
						vac_lines[line.employee_id.id] = line
						# line.month_line_ids.unlink()

					if line.employee_id.id not in employee_months:
						employee_months[line.employee_id.id] = {'months': {}}
					
					for mon in line.month_line_ids:
						if mon.month_id.id not in employee_months[line.employee_id.id]['months']:
							employee_months[line.employee_id.id]['months'][mon.month_id.id] = mon.month_id.id

				for employee in employees:
					if employee.id not in vac_lines:
						new_line = self.env['llp.payroll.employee.vacation.line'].create({
							'employee_id': employee.id,
							'vacation_id': vac.id,
						})
						vac_lines[employee.id] = new_line
						employee_months[employee.id] = {'months': {}}
					else:
						if employee.id not in employee_months:
							employee_months[employee.id] = {'months': {}}


	def action_check_lines(self):
		employees = []
		if not self.line_ids:
			raise UserError((u'Мөр хоосон байна.'))

		for line in self.line_ids:
			if line.employee_id.id not in employees:
				employees.append(line.employee_id.id)
			else:
				raise UserError((u'%s ажилтан дээр 2 амралт бодох гэж байна.'%(line.employee_id.name)))


class LLPPayrollEmployeeVacationLine(models.Model):
	_name ='llp.payroll.employee.vacation.line'
	_inherit = ['mail.thread']
	_description = "LLP payroll vacation line"
	_order = "create_date desc"


	def _compute_total(self):
		total_worked_day = 1
		for line in self:		
			line.total_salary = sum(line.salary for line in line.month_line_ids)	
			line.total_worked_day = sum(line.worked_day for line in line.month_line_ids)
			if line.total_worked_day !=0:
				total_worked_day = line.total_worked_day				
			line.one_day_salary = line.total_salary / total_worked_day
			line.total_vacation_amount = line.total_vacation_day * line.one_day_salary

	# TODO: employee_id domain vacation_id.department_ids
	employee_id = fields.Many2one(
		'hr.employee',
		string="Employee",
		required=True,
		tracking=True
	)
	department_id = fields.Many2one('hr.department', string="Department", related='employee_id.department_id', store=True, readonly=True)
	total_salary = fields.Float(string="11 months total salary",compute='_compute_total',digits=(16,2))
	total_worked_day =fields.Float(string="11 months total work days",compute='_compute_total',digits=(16,2))
	one_day_salary = fields.Float(string="One day salary", compute='_compute_total',digits=(16,2))	
	total_vacation_day = fields.Float(string="Total vacation days",digits=(16,2))
	total_vacation_amount = fields.Float(string="Total vacation amount",compute= '_compute_total',digits=(16,2))
	month_line_ids = fields.One2many('llp.payroll.employee.month.line','line_id',string="Month lines")
	vacation_id = fields.Many2one('llp.payroll.employee.vacation', string="Vacation")
	month = fields.Date(string="Month", related="vacation_id.month", required=True, tracking=True)


class LLPPayrollEmployeeMonthLine(models.Model):
	_name = 'llp.payroll.employee.month.line'
	_order = 'month desc'
	_description = "LLP payroll employee month line"

	month = fields.Date(string="Month", required=True, tracking=True)
	salary = fields.Float(string="Salary")
	worked_day = fields.Float(string="Worked day",digits=(16,5))
	line_id = fields.Many2one('llp.payroll.employee.vacation.line',string="Vacation",ondelete='cascade')

class LLPPayrollVacationHistory(models.Model):
	_inherit = 'request.history'

	payroll_vacation_id = fields.Many2one('llp.payroll.employee.vacation', string='Payroll Vacation', ondelete="cascade")
