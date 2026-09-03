# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from datetime import date, datetime, timedelta
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
	month = fields.Date(string="Month",required=True, tracking=True)
	department_ids = fields.Many2many('hr.department', string="Departments", tracking=True)
	dynamic_workflow_id = fields.Many2one('dynamic.workflow', string="Dynamic workflow")
	struct_type = fields.Selection([('salary_advance','Salary advance'),('salary_late','Salary late')],string="Type")
	state = fields.Selection([
		('draft', 'Draft'), # Ноорог
		('pending', 'Pending Approval'), # Зөвшөөрөл хүлээж буй
		('done', 'Done'), # Батлагдсан
		('locked', 'Locked'), # Түгжигдсэн
	], string="State", default='draft', tracking=True)
	line_ids = fields.One2many('llp.payroll.employee.vacation.line','vacation_id',string="Lines")
	history_ids = fields.One2many('request.history','payroll_vacation_id',string="State History")
	company_id = fields.Many2one('res.company', string="Company",default=lambda self: self.env.company,)


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
			if not vac.department_ids:
				raise UserError(_("Алба нэгж сонгоно уу."))

			today = fields.Date.context_today(vac)
			prev_month_end = (today.replace(day=1) - timedelta(days=1))
			emp_domain = [
				('active', '=', False),
				('department_id', 'in', vac.department_ids.ids),
				('last_vacation_salary_date', '!=', False),
			]
			if vac.company_id:
				emp_domain.append(('company_id', '=', vac.company_id.id))
			employees = self.env['hr.employee'].sudo().search(emp_domain)
			# struct_type-с хамааран next_vacation_salary_date-ийн өдрөөр шүүх
			if vac.struct_type == 'salary_advance':
				employees = employees.filtered(
					lambda e: e.next_vacation_salary_date
					and e.next_vacation_salary_date.year == vac.month.year
					and e.next_vacation_salary_date.month == vac.month.month
					and 1 <= e.next_vacation_salary_date.day <= 15
				)
			elif vac.struct_type == 'salary_late':
				employees = employees.filtered(
					lambda e: e.next_vacation_salary_date
					and e.next_vacation_salary_date.year == vac.month.year
					and e.next_vacation_salary_date.month == vac.month.month
					and e.next_vacation_salary_date.day >= 16
				)

			line_by_emp = {l.employee_id.id: l for l in vac.line_ids if l.employee_id}
			for emp in employees:
				if emp.id not in line_by_emp:
					line_by_emp[emp.id] = self.env['llp.payroll.employee.vacation.line'].create({
						'employee_id': emp.id,
						'vacation_id': vac.id,
					})

			if not line_by_emp:
				continue

			all_lines = self.env['llp.payroll.employee.vacation.line'].browse([l.id for l in line_by_emp.values()])
			all_lines.mapped('month_line_ids').unlink()

			struct_ids = self.env['llp.payroll.structure'].sudo().search([
				('struct_type', '=', 'salary_late')
			]).ids
			if not struct_ids:
				raise UserError(_("Сарын сүүл төрөлтэй цалингийн бүтэц олдсонгүй."))

			self.env.cr.execute("""
				SELECT DISTINCT r.id
				FROM llp_payroll_structure_line sl
				JOIN llp_payroll_rule r ON r.id = sl.rule_id
				WHERE sl.struct_id = ANY(%s)
					AND (r.is_vacation_salary = TRUE OR r.is_vacation_time = TRUE)
			""", (struct_ids,))
			rule_ids = [r[0] for r in self.env.cr.fetchall()]
			if not rule_ids:
				continue

			emp_start_map = {}
			earliest_start = None
			for emp in employees:
				d = emp.last_vacation_salary_date
				start = d.replace(day=1)
				emp_start_map[emp.id] = start
				if earliest_start is None or start < earliest_start:
					earliest_start = start

			if earliest_start and earliest_start > prev_month_end:
				continue
			m2m_field = self.env['llp.payroll']._fields['department_id']
			rel_table = m2m_field.relation
			rel_col1 = m2m_field.column1
			rel_col2 = m2m_field.column2
			query = f"""
				SELECT
					pl.employee_id AS employee_id,
					date_trunc('month', p.start_date)::date AS month,
					SUM(CASE WHEN r.is_vacation_salary = TRUE THEN COALESCE(rv.value, 0) ELSE 0 END) AS salary,
					SUM(CASE WHEN r.is_vacation_time = TRUE THEN COALESCE(rv.value, 0) ELSE 0 END) / 8 AS worked_day
				FROM llp_payroll p
				JOIN llp_payroll_line pl ON pl.payroll_id = p.id
				JOIN llp_payroll_rule_value rv ON rv.line_id = pl.id
				JOIN llp_payroll_rule r ON r.id = rv.payroll_rule_id
				JOIN llp_payroll_structure s ON s.id = p.struct_id
				WHERE p.state = 'confirmed'
					AND EXISTS (
						SELECT 1
						FROM {rel_table} rel
						WHERE rel.{rel_col1} = p.id
							AND rel.{rel_col2} = ANY(%s)
					)
					AND p.end_date <= %s
					AND p.start_date >= %s
					AND s.struct_type = 'salary_late'
					AND r.id = ANY(%s)
				GROUP BY pl.employee_id, date_trunc('month', p.start_date)::date
				ORDER BY pl.employee_id, month
			"""

			self.env.cr.execute(query, (
				vac.department_ids.ids,
				prev_month_end,
				earliest_start,
				rule_ids,
			))
			rows = self.env.cr.fetchall()

			by_emp = {}
			for emp_id, mon, sal, wd in rows:
				by_emp.setdefault(emp_id, []).append((mon, float(sal or 0.0), float(wd or 0.0)))

			MonthLine = self.env['llp.payroll.employee.month.line']
			create_vals = []

			for emp_id, line in line_by_emp.items():
				emp_start = emp_start_map.get(emp_id)
				if not emp_start:
					continue

				for mon, sal, wd in by_emp.get(emp_id, []):
					if mon < emp_start:
						continue
					if mon > prev_month_end.replace(day=1):
						continue

					create_vals.append({
						'line_id': line.id,
						'month': mon,
						'salary': sal,
						'worked_day': wd,
					})
			if create_vals:
				MonthLine.create(create_vals)

		return True

	# def action_get_data(self):
	# 	for vac in self:
	# 		if not vac.department_ids:
	# 			raise UserError(_("Алба нэгж сонгоно уу."))

	# 		today = fields.Date.context_today(vac)
	# 		prev_month_end = (today.replace(day=1) - timedelta(days=1))

	# 		employees = self.env['hr.employee'].sudo().search([
	# 			('active', '=', True),
	# 			('department_id', 'in', vac.department_ids.ids),
	# 			('last_vacation_salary_date', '!=', False),
	# 		])

	# 		line_by_emp = {l.employee_id.id: l for l in vac.line_ids if l.employee_id}
	# 		for emp in employees:
	# 			if emp.id not in line_by_emp:
	# 				line_by_emp[emp.id] = self.env['llp.payroll.employee.vacation.line'].create({
	# 					'employee_id': emp.id,
	# 					'vacation_id': vac.id,
	# 				})

	# 		if not line_by_emp:
	# 			continue

	# 		all_lines = self.env['llp.payroll.employee.vacation.line'].browse([l.id for l in line_by_emp.values()])
	# 		all_lines.mapped('month_line_ids').unlink()

	# 		struct_ids = self.env['llp.payroll.structure'].sudo().search([
	# 			('struct_type', '=', 'salary_late')
	# 		]).ids
	# 		if not struct_ids:
	# 			raise UserError(_("Сарын сүүл төрөлтэй цалингийн бүтэц олдсонгүй."))

	# 		self.env.cr.execute("""
	# 			SELECT DISTINCT r.id
	# 			FROM llp_payroll_structure_line sl
	# 			JOIN llp_payroll_rule r ON r.id = sl.rule_id
	# 			WHERE sl.struct_id = ANY(%s)
	# 				AND (r.is_vacation_salary = TRUE OR r.is_vacation_time = TRUE)
	# 		""", (struct_ids,))
	# 		rule_ids = [r[0] for r in self.env.cr.fetchall()]
	# 		if not rule_ids:
	# 			continue

	# 		emp_start_map = {}
	# 		earliest_start = None
	# 		for emp in employees:
	# 			d = emp.last_vacation_salary_date
	# 			start = d.replace(day=1)
	# 			emp_start_map[emp.id] = start
	# 			if earliest_start is None or start < earliest_start:
	# 				earliest_start = start

	# 		if earliest_start and earliest_start > prev_month_end:
	# 			continue

	# 		self.env.cr.execute("""
	# 			SELECT
	# 				pl.employee_id AS employee_id,
	# 				date_trunc('month', p.start_date)::date AS month,
	# 				SUM(CASE WHEN r.is_vacation_salary = TRUE THEN COALESCE(rv.value, 0) ELSE 0 END) AS salary,
	# 				SUM(CASE WHEN r.is_vacation_time   = TRUE THEN COALESCE(rv.value, 0) ELSE 0 END)/8 AS worked_day
	# 			FROM llp_payroll p
	# 			JOIN llp_payroll_line pl ON pl.payroll_id = p.id
	# 			JOIN llp_payroll_rule_value rv ON rv.line_id = pl.id
	# 			JOIN llp_payroll_rule r ON r.id = rv.payroll_rule_id
	# 			JOIN llp_payroll_structure s ON s.id = p.struct_id
	# 			WHERE p.state = 'confirmed'
	# 				AND p.department_id = ANY(%s)
	# 				AND p.end_date <= %s
	# 				AND p.start_date >= %s
	# 				AND s.struct_type = 'salary_late'
	# 				AND r.id = ANY(%s)
	# 			GROUP BY pl.employee_id, date_trunc('month', p.start_date)::date
	# 			ORDER BY pl.employee_id, month
	# 		""", (vac.department_ids.ids, prev_month_end, earliest_start, rule_ids))

	# 		rows = self.env.cr.fetchall()

	# 		by_emp = {}
	# 		for emp_id, mon, sal, wd in rows:
	# 			by_emp.setdefault(emp_id, []).append((mon, float(sal or 0.0), float(wd or 0.0)))

	# 		MonthLine = self.env['llp.payroll.employee.month.line']
	# 		create_vals = []

	# 		for emp_id, line in line_by_emp.items():
	# 			emp_start = emp_start_map.get(emp_id)
	# 			if not emp_start:
	# 				continue

	# 			for mon, sal, wd in by_emp.get(emp_id, []):
	# 				if mon < emp_start:
	# 					continue
	# 				if mon > prev_month_end.replace(day=1):
	# 					continue

	# 				create_vals.append({
	# 					'line_id': line.id,
	# 					'month': mon,
	# 					'salary': sal,
	# 					'worked_day': wd,
	# 				})

	# 		if create_vals:
	# 			MonthLine.create(create_vals)

	# 	return True


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
			if line.total_vacation_day == False:
				line.total_vacation_day = line.employee_id.annual_leave_remaining_days
			line.total_salary = sum(line.salary for line in line.month_line_ids)	
			line.total_worked_day = sum(line.worked_day for line in line.month_line_ids)
			if line.total_worked_day !=0:
				total_worked_day = line.total_worked_day				
			line.one_day_salary = line.total_salary / total_worked_day
			line.total_vacation_amount = line.total_vacation_day * line.one_day_salary

	def _onchange_total_vacation_day(self):
		if self.total_vacation_day == 0:
			self.total_vacation_day = self.employee_id.annual_leave_remaining_days
		

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
	done_or_not = fields.Boolean(string="Done or Not", store=True, default=False)


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
