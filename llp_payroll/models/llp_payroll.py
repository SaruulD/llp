# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from datetime import timedelta,datetime
from dateutil.relativedelta import relativedelta
import logging
import json
_logger = logging.getLogger(__name__)
import time
from operator import itemgetter
from zeep import Client
from odoo.tools import exception_to_unicode # type: ignore

class LLPPayroll(models.Model):
    _name = 'llp.payroll'
    _inherit = ['mail.thread']
    _description = "LLP payroll"
    _order = "create_date desc"

    code = fields.Char(string="Code")
    date = fields.Date(string="Month",required=True, tracking=True)
	
    department_id = fields.Many2one('hr.department',string="Department",tracking=True)
	
    struct_id = fields.Many2one('llp.payroll.structure',string="Stucture", domain="[('state','=','done')]",tracking=True)
    struct_type = fields.Selection([('salary_advance','Salary advance'),('salary_late','Salary late')],string="Structure type")
    line_ids = fields.One2many('llp.payroll.line','payroll_id',string="Lines")
	
	
    state = fields.Selection([
        ('draft','Draft'),
        ('sent','Sent'),
        ('approved','Approved'),
        ('verified','Verified'),
        ('confirmed','Confirmed'),
        ('done','Done'),
        ('closed','Closed')
    ],string='State',default='draft',tracking=True)
    # move_id = fields.Many2one('account.move', string="Move")
    # millionaire_request_id = fields.Many2one('millionaire.fund.request',string="Millionaire payment request")
    # confirm_user_ids = fields.Many2many(comodel_name='res.users',string="Confirm users")
    # active_sequence = fields.Integer(string="Active sequence",default="1")
    # is_sent = fields.Boolean(string="Is sent", default=False, compute = '_is_sent')
    # is_verify = fields.Boolean(string="Is verified", default=False, compute = '_is_verify')
    # is_approve = fields.Boolean(string="Is approved", default=False, compute = '_is_approve')
    # is_confirm = fields.Boolean(string="Is confirmed", default=False, compute = '_is_confirm')
    # is_salary_request = fields.Boolean(string="Is salary request", default=False)
    # is_fund_request = fields.Boolean(string="Is salary request", default=False)
    # is_bonus_request = fields.Boolean(string="Is bonus request", default=False)
    # is_coin_request = fields.Boolean(string="Is bonus request", default=False)
    # is_amendment = fields.Boolean(string="Is salary amendment", default=False)
    # is_diamond = fields.Boolean(string="Is  diamond", default=False)
    # is_millionaire_request = fields.Boolean(string="Is  millionaire request", default=False)
    # history_ids = fields.One2many('request.history','payroll_id',string="History")
    # is_sent_message = fields.Boolean(string="Is send message", default=False)
    # payment_history_ids = fields.One2many('payroll.payment.history', 'payroll_id', string="Payment history")
    # nes_history_ids = fields.One2many('millionaire.nes.history', 'payroll_id', string="millionaire nes history")
    # approved_emp=fields.Char(string="Approved Emp")
    # confirm_emp=fields.Char(string="Confirm Emp")
    # is_millionaire_payment_request = fields.Boolean(string="Is millionaire payment request", default=False)

    @api.depends('date')
    def _compute_year_month(self):
        for rec in self:
            if rec.date:
                rec.year = rec.date.strftime('%Y')
                rec.month = rec.date.strftime('%m')
            else:
                rec.year = rec.month = False
		
# class LLPPayrollLine(models.Model):
# 	_name = 'llp.payroll.line'
# 	_description = "LLP payroll line"
# 	_order = "name asc"

# 	name = fields.Char(related="payroll_employee_id.name",string="Name", store=True,index=True)
# 	payroll_id = fields.Many2one('nomin.payroll',string="Payroll",ondelete='cascade',index=True)
# 	month_id = fields.Many2one('account.period',string="Month",related="payroll_id.month_id" , index=True)
# 	payroll_employee_id = fields.Many2one('nomin.payroll.employee',string="Employee", ondelete="restrict",index=True)
# 	register = fields.Char(related="payroll_employee_id.register", string="Register",index=True)
# 	rule_value_ids = fields.One2many('nomin.payroll.rule.value','line_id', string="Value")
	
	
# 	def action_computebyQUERY(self):
# 		if not self.rule_value_ids:
# 			rules = []
# 			for line in self.payroll_id.struct_id.line_ids:
# 				is_edit =False
# 				if line.rule_id.ruleview_type=='edit':
# 					is_edit = True
# 				rules.append((0,0,{'payroll_rule_id':line.rule_id.id,'show_in_payroll':line.rule_id.show_in_payroll,'decimal_point':line.rule_id.decimal_point,'rulefield_type':line.rule_id.rulefield_type,'sequence':line.sequence,'is_sum_view':line.rule_id.is_check,'value':0,'is_edit':is_edit}))	
# 			self.write({'rule_value_ids':rules})
# 		self.env.cr.commit()	
# 		starttime = time.time()			
# 		query = "select C.id as rule_value_id,D.rule_type as rule_type, D.rulefield_type as rulefield_type, D.value_type as value_type, \
# 					G.employee_id as employee , D.ruleview_type as ruleview_type,D.code as code, B.id as line_id, D.python_code as python_code, F.exp_sequence as exp_sequence,G.id as payroll_employee, C.is_edited as is_edited\
# 					from nomin_payroll A inner join nomin_payroll_line B ON A.id= B.payroll_id \
# 						inner join nomin_payroll_rule_value C on B.id=C.line_id \
# 						inner join nomin_payroll_rule D on D.id=C.payroll_rule_id \
# 						left join nomin_payroll_structure E ON E.id= A.struct_id \
# 						left join nomin_payroll_structure_line F ON F.struct_id= E.id and F.rule_id=D.id\
# 						inner join nomin_payroll_employee G ON G.id=B.payroll_employee_id \
# 				where A.id=%s and B.id=%s group by rule_value_id, rule_type, D.rulefield_type,  value_type, employee, ruleview_type, code,B.id,\
# 					python_code, exp_sequence,payroll_employee,is_edited order by F.exp_sequence asc "%(self.payroll_id.id,self.id) 		
# 		self.env.cr.execute(query)		
# 		dictfetchall = self.env.cr.dictfetchall()	
# 		sheet_obj= self.env['hr.employee.attendance.sheet1']
# 		formulas = {}
# 		if dictfetchall:
# 			count=0
# 			for dic in dictfetchall:
# 				group = dic ['exp_sequence'] 
# 				if group not in formulas:
# 					formulas[group] = {
# 						'exp_sequence':0,
# 						'rules':{},						
# 					}
# 				formulas[group]['exp_sequence'] = group
# 				group1 = dic['code']
# 				if group1 not in formulas[group]['rules']:
# 					formulas[group]['rules'][group1]={
# 						'code':'',
# 						'python_code':'',
# 						'rule_type':'',
# 						'value_type':'',
# 						'rulefield_type':'',
# 						'employees':{}
# 					}
# 				formulas[group]['rules'][group1]['code'] = group1
# 				formulas[group]['rules'][group1]['python_code'] = dic['python_code']
# 				formulas[group]['rules'][group1]['rule_type'] = dic['rule_type']
# 				formulas[group]['rules'][group1]['value_type'] = dic['value_type']
# 				formulas[group]['rules'][group1]['rulefield_type'] = dic['rulefield_type']
# 				group2 = dic['employee']
# 				if group2 not in formulas[group]['rules'][group1]['employees']:
# 					formulas[group]['rules'][group1]['employees'][group2] = {
# 						'employee':0,
# 						'payroll_employee':0,
# 						'rule_value_id': 0,
# 						'line_id': 0,
# 						'is_edited':False,
# 					}
# 				formulas[group]['rules'][group1]['employees'][group2]['employee'] = dic['employee']
# 				formulas[group]['rules'][group1]['employees'][group2]['rule_value_id'] = dic['rule_value_id']
# 				formulas[group]['rules'][group1]['employees'][group2]['payroll_employee'] = dic['payroll_employee'] 
# 				formulas[group]['rules'][group1]['employees'][group2]['line_id'] = dic['line_id'] 
# 				formulas[group]['rules'][group1]['employees'][group2]['is_edited'] = dic['is_edited'] 
# 		if formulas:
# 			endtime = time.time()						
# 			for formula in sorted(formulas.values(), key=itemgetter('exp_sequence')):				
# 				for ruled in sorted(formula['rules'].values(), key=itemgetter('code')):
# 					count =0
# 					for emp in sorted(ruled['employees'].values(), key=itemgetter('employee')):
# 						attend =False
# 						value = None
# 						if self.payroll_id.struct_type!='bonus':
# 							if self.payroll_id.struct_type=='salary_advance':
# 								struct_type = 'salary_advance'
# 							else:
# 								struct_type = 'salary_late'
# 							query_sheet = "select id from hr_employee_attendance_sheet1 where period_id=%s and employee_id=%s and struct_type ='%s' and state='confirmed'"%(self.payroll_id.month_id.id,emp['employee'],struct_type)
# 							fetch = False
# 							try:							
# 								self.env.cr.execute(query_sheet)
# 								fetch=self.env.cr.fetchone()						
								
# 							except:
# 								self.env.cr.rollback()
							
							
# 							if fetch:
# 								attend = sheet_obj.sudo().browse(fetch[0])
# 						rule = False				
						
# 						if emp['rule_value_id']:
# 							rule = self.env['nomin.payroll.rule.value'].browse(emp['rule_value_id'])						
						
# 						if ruled['code'] in ['n32012','n35038','n35037','n35051','n35052']:						
# 							query = "select B.id from nomin_payroll_salary_gap A left join payroll_salary_gap B ON A.id=B.salary_gap_id where A.state in ('confirmed','closed') and B.payroll_employee_id = %s and A.month_id =%s and A.struct_type='%s'"%(emp['payroll_employee'],self.payroll_id.month_id.id,self.payroll_id.struct_type)
# 							self.env.cr.execute(query)
# 							fetch = self.env.cr.fetchone()							
# 							if fetch and fetch[0]:
# 								attend = self.env['payroll.salary.gap'].browse(fetch[0])
# 								python_code = ruled['python_code'][7:]
# 								value = eval(python_code)
# 								if value!=0:
# 									self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(value,emp['rule_value_id']))
# 									self.env.cr.commit()
# 						# Зөрүү цалин
# 						elif ruled['code'] in ['n35021','n35050','n35049','n35053','n35054']:							
# 							# n35021
# 							query = "select B.id from nomin_payroll_gap A inner join payroll_gap_employee B ON A.id=B.payroll_gap_id where A.state in ('confirmed','closed') and B.payroll_employee_id = %s and A.month_id =%s and A.struct_type='%s'"%(emp['payroll_employee'],self.payroll_id.month_id.id,self.payroll_id.struct_type)
# 							self.env.cr.execute(query)
# 							fetch = self.env.cr.fetchone()	
# 							is_used = True						
# 							if fetch and fetch[0]:
# 								attend = self.env['payroll.gap.employee'].browse(fetch[0])
# 								python_code = ruled['python_code'][7:]
								
# 								value = eval(python_code)
# 								if emp['is_edited']==False:	
# 									self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(value,emp['rule_value_id']))
# 									self.env.cr.commit()
# 						elif ruled['code'] in ['n33001','n80001','n33004','n80058']:	
# 										query_sheet = "select A.id from payroll_employee_debt_line A inner join nomin_payroll_employee_debt B ON A.debt_id=B.id where B.month_id=%s and A.employee_id=%s and B.struct_type='%s' and B.state in ('confirmed')"%(self.payroll_id.month_id.id,emp['employee'],self.payroll_id.struct_type)
# 										self.env.cr.execute(query_sheet)
# 										fetch=self.env.cr.fetchone()
# 										attend =False
# 										python_code = ruled['python_code'][7:]
# 										if fetch and fetch[0]:
# 											attend = self.env['payroll.employee.debt.line'].sudo().browse(fetch[0])										
# 											value = eval(python_code)																				
											
# 											self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(value,emp['rule_value_id']))
# 											self.env.cr.commit()
# 										# else:			
# 										# 	self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(0.0,emp['rule_value_id']))
# 										# 	self.env.cr.commit()
# 						# Ээлжийн амралт
# 						elif ruled['code'] in ['n35022','n35005']:
# 							query = "select B.id from nomin_payroll_employee_vacation A inner join payroll_employee_vacation_line B ON A.id=B.vacation_id where A.state in ('confirmed','closed') and B.payroll_employee_id = %s and A.month_id =%s and A.struct_type='%s'"%(emp['payroll_employee'],self.payroll_id.month_id.id,self.payroll_id.struct_type)
# 							# _logger.info("\n\n\n query = %s"%query)
# 							self.env.cr.execute(query)
# 							fetch = self.env.cr.fetchone()		
# 							is_used = True					
# 							if fetch and fetch[0]:
# 								attend = self.env['payroll.employee.vacation.line'].browse(fetch[0])
# 								python_code = ruled['python_code'][7:]
# 								value = eval(python_code)
# 								self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(value,emp['rule_value_id']))
# 								self.env.cr.commit()		
# 						elif ruled['code'] in ['n35025','n35024','n35003','n35002']:		
# 							python_code = ruled['python_code'][7:]
# 							query_sheet = "select A.id from payroll_employee_disability_line A inner join nomin_payroll_employee_disability B ON A.disability_id=B.id where B.month_id=%s and A.employee_id=%s and B.calculate='%s' and B.state in ('confirmed','closed')"%(self.payroll_id.month_id.id,emp['employee'],self.payroll_id.struct_type)
# 							self.env.cr.execute(query_sheet)
# 							dictfetchall=self.env.cr.dictfetchall()
# 							attend =False																			
# 							sum_value =0
# 							if self.payroll_id.struct_type=='salary_late' and ruled['code'] in ['n35002']:
# 								query_sheet = "select A.id as id,B.id as bid from payroll_employee_disability_line A inner join nomin_payroll_employee_disability B ON A.disability_id=B.id where B.month_id=%s and A.employee_id=%s and B.calculate='%s' and B.state in ('confirmed','closed')"%(self.payroll_id.month_id.id,emp['employee'],'salary_advance')
# 								self.env.cr.execute(query_sheet)
# 								fetchall=self.env.cr.dictfetchall()
# 								if fetchall:
# 									for dic in fetchall:
# 										attend = self.env['payroll.employee.disability.line'].sudo().browse(dic['id'])									
# 										sum_value+= eval(python_code)
									
# 							if sum_value>0 or dictfetchall:
# 								if dictfetchall:
# 									for dic in dictfetchall:
# 										attend = self.env['payroll.employee.disability.line'].sudo().browse(dic['id'])									
# 										sum_value+= eval(python_code)
															
# 								value = sum_value
								
# 								self.env.cr.execute('update nomin_payroll_rule_value set value=%s,is_edited=True where id=%s'%(value,emp['rule_value_id']))
# 								self.env.cr.commit()
# 							else:
# 								self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(0.0,emp['rule_value_id']))
# 								self.env.cr.commit()

# 						elif ruled['code'] in ['n35011']:		
# 								query_sheet = "select A.id from payroll_maternity_leave_line A left join nomin_payroll_maternity_leave B ON A.leave_id=B.id where B.month_id=%s and A.employee_id=%s and B.type='%s' and B.state in ('confirmed','closed') "%(self.payroll_id.month_id.id,emp['employee'],self.payroll_id.struct_type)
# 								self.env.cr.execute(query_sheet)
# 								dictfetchall=self.env.cr.dictfetchall()
# 								attend =False	
# 								python_code = ruled['python_code'][7:]
# 								if dictfetchall:
# 									sum_value =0
# 									for dic in dictfetchall:
# 										attend = self.env['payroll.maternity.leave.line'].sudo().browse(dic['id'])																			
# 										sum_value+= eval(python_code)
# 									value = sum_value												
# 									self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(value,emp['rule_value_id']))
# 									self.env.cr.commit()
# 								else:
# 									self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(0.0,emp['rule_value_id']))
# 									self.env.cr.commit()
# 						elif ruled['rule_type']=='code':
# 							python_code = ruled['python_code'][7:]
							
# 							if ruled['value_type']=='expression':
# 								sheetstarttime = time.time()	

# 								rule_codes = re.findall('n\d+',str(python_code))
# 								if rule_codes:
# 									where ="where A.line_id = %s "%emp['line_id']
# 									if len(rule_codes)>1:
# 											where=where+" and B.code in %s"%(str(tuple(rule_codes)))
# 									else:				
# 											where=where+" and B.code = '%s'"%(str(rule_codes[0]))
# 									query="select A.value as value, B.code as code from nomin_payroll_rule_value A inner join nomin_payroll_rule B ON A.payroll_rule_id = B.id "+where																
# 									sheetstarttime = time.time()			
# 									self.env.cr.execute(query)
# 									fetchedAll = self.env.cr.dictfetchall()
# 									if ruled['code']=='n32011':
# 										sheetendtime = time.time()											
										
# 									if fetchedAll:
# 										for fetched in fetchedAll:											
# 											python_code = python_code.replace(fetched['code'],str(fetched['value']))									
								
							
# 							if ruled['rulefield_type'] in ('bonus','monthly_bonus'):
# 								if self.payroll_id.struct_type in ('bonus','monthly_bonus'):
# 									value = self.payroll_id.get_bonus_code(python_code,rule,emp['payroll_employee'])
# 								else:
# 									if rule_codes:
# 										value=0
# 										for code in rule_codes:
# 											value += self.payroll_id.get_from_bonus(emp['payroll_employee'],code,self.payroll_id.month_id.id,ruled['rulefield_type'])
										
# 									else:
# 											value = self.payroll_id.get_from_bonus(emp['payroll_employee'],python_code,self.payroll_id.month_id.id,ruled['rulefield_type'])
# 								if emp['is_edited']==False:
# 									self.env.cr.execute("update nomin_payroll_rule_value set value=%s where id=%s"%(value,emp['rule_value_id']))
# 							if ruled['rulefield_type']=='from_previous_month':
# 									value = self.payroll_id.get_from_previous_month(emp['payroll_employee'],python_code,self.payroll_id.month_id)								
# 									if emp['is_edited']==False:
# 										self.env.cr.execute("update nomin_payroll_rule_value set value=%s where id=%s"%(value,emp['rule_value_id']))				
# 							elif ruled['rulefield_type']=='profit_bonus':
# 								value = self.payroll_id.get_from_profitbonus(emp['payroll_employee'],python_code,self.month_id.id)
# 								self.env.cr.execute("update nomin_payroll_rule_value set value=%s where id=%s"%(value,emp['rule_value_id']))	
# 							try:								
# 								if ruled['rulefield_type']=='salary_advance':
# 									value = self.payroll_id.get_from_advance(emp['payroll_employee'],python_code,self.month_id.id)									
									
# 									self.env.cr.execute("update nomin_payroll_rule_value set value=%s where id=%s"%(value,emp['rule_value_id']))								
									
								
# 								else:
# 									rule_codes = re.findall('n\d+',str(python_code))			
# 									if rule_codes:
# 										for code in rule_codes:
# 											python_code = python_code.replace(code,str(0))									
									
# 									value = eval(python_code)

# 									if ruled['code'] =='n31005' and value>0:											
# 										employee_id = self.env['hr.employee'].browse(emp['employee'])
# 										if employee_id.job_id:
# 											# if employee_id.job_id.below_than_stockkeeper and value >16:
# 											# 	value = 16
# 											# elif not employee_id.job_id.below_than_stockkeeper:
# 											# 	value = 0
# 											# BEFORE COVID 19
# 											if employee_id.job_id.below_than_stockkeeper and value >60:

# 												value = 60

# 											elif not employee_id.job_id.below_than_stockkeeper and value >30:
# 												self.env.cr.execute("SELECT COUNT(*) FROM generate_series(timestamp %s, %s, '1 day') AS g(mydate) WHERE EXTRACT(DOW FROM mydate) = 6",(self.payroll_id.month_id.date_start,self.payroll_id.month_id.date_stop))
# 												count_saturdays = self.env.cr.fetchone()[0]
# 												if count_saturdays>4:
# 													if value>20:
# 														value = 20
# 												else:
# 													value = 30

# 									if ruled['code']=='n10005':										
# 										if self.payroll_id.struct_type=='salary_late':
# 											query="select B.salary from hr_employee A left join hr_history B ON A.id = B.employee_id and  B.salary is not null and B.date is not null where B.employee_id = %s and B.confirm_date <='%s' order by B.date desc, B.confirm_date desc,B.create_date desc limit 1"%(emp['employee'],self.payroll_id.month_id.date_stop)
											
# 										else:											
# 											last_month = self.payroll_id.month_id.date_stop-relativedelta(days=13)											
# 											query="select B.salary from hr_employee A left join hr_history B ON A.id = B.employee_id and B.salary is  not null and B.date is not null where B.employee_id = %s and B.confirm_date <='%s' order by B.date desc, B.confirm_date desc,B.create_date desc limit 1"%(emp['employee'],last_month)
# 										try:							
# 											self.env.cr.execute(query)
# 											fetch = self.env.cr.fetchone()							
											

# 											if fetch:												
# 												value = fetch[0]
# 											else :												
# 												if self.struct_type=='salary_late':
# 													query="select B.salary from hr_employee A left join hr_history B ON A.id = B.employee_id and  B.salary is not null and B.date is not null where B.employee_id = %s and B.confirm_date <='%s' order by B.date desc, B.confirm_date desc,B.create_date desc limit 1"%(emp['employee'],self.payroll_id.month_id.date_stop)
# 												else:													
# 													last_month = self.payroll_id.month_id.date_stop-relativedelta(days=13)															
# 													query="select B.salary from hr_employee A left join hr_history B ON A.id = B.employee_id and  B.salary is not null and B.date is not null where B.employee_id = %s and B.confirm_date <='%s'  order by B.date desc, B.confirm_date desc,B.create_date desc limit 1"%(emp['employee'],last_month)

# 												self.env.cr.execute(query)
# 												fetch = self.env.cr.fetchone()							
# 												if fetch:
# 													value = fetch[0]
# 											if value==0 or value is None:
# 												value = eval(python_code)
# 										except:
# 											self.env.cr.rollback()
# 									count+=1									

# 									if ruled['rulefield_type']=='digit':
# 										if not value:
# 											value = 0
# 										if emp['is_edited']==False:
# 											self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(value,emp['rule_value_id'])) 
# 									elif ruled['rulefield_type']=='sign':
# 										self.env.cr.execute("update nomin_payroll_rule_value set char_value='%s' where id=%s"%(value,emp['rule_value_id']))
								
								
# 								self.env.cr.commit()
# 							except Exception as e:
# 									# raise UserError(_(u'Алдаа: %s '%(exception_to_unicode(e))))
# 									if ruled['rulefield_type']=='digit':																			
# 										self.env.cr.execute('update nomin_payroll_rule_value set value=%s where id=%s'%(0,emp['rule_value_id']))
# 									elif ruled['rulefield_type']=='sign':									
# 										self.env.cr.execute("update nomin_payroll_rule_value set char_value='%s' where id=%s"%(False,emp['rule_value_id']))	
# 									pass
									
	
# 	# Ажилтаны мөр дээрх утга буцаах
# 	@api.model
# 	def get_values(self,lines,fields):
# 		line_ids = []			
# 		line_ids = self.search([('id','in',lines)])
# 		line_obj = {}
# 		for line in line_ids:
# 			for  field in fields:
# 				if field in line:	
# 					if type(line[field]) is str or type(line[field]) is int or type(line[field]) is float:
# 						line_obj[field]= line[field]
# 					else:
# 						line_obj[field]= line[field].id			
# 		return line_obj

# 	@api.model
# 	def get_line_values(self, payroll_id):
# 		payroll_id = self.env['nomin.payroll'].search([('id','=',payroll_id)])
# 		lines = {}
# 		employees = []
# 		rules = [] 
# 		employee_values = {}
# 		employee_lines = {}
# 		is_edits = {}
# 		is_signs = {}
# 		decimals = {}
# 		sum_rules = {}
		
# 		struct_id = False
# 		start = time.time()		
# 		_logger.info("\n\n\n\n\n LOGGER START TIME = '%s'"%start)
# 		# where=" where A.id in %s"%(str(tuple(line_ids)))
# 		# query="select D.id as payroll_employee_id, from nomin_payroll_line A inner join nomin_payroll_rule_value B ON A.id=B.line_id \
# 		# 		inner join nomin_payroll_rule inner join nomin_payroll_employee D ON D.id=A.payroll_employee_id inner join hr_employee E ON E.id=D.employee_id"

# 		# query=query+where
# 		# self.env.cr.execute(query)
# 		# dictfetchall = self.env.cr.dictfetchall()
# 		# if dictfetchall:
# 		# 	for dic in dictfetchall:
				
# 		# 		employees.append([line.payroll_employee_id.id,line.payroll_employee_id.name+' '+line.payroll_employee_id.last_name])	
# 		for obj in payroll_id.line_ids:
# 			line = obj.sudo()
# 			struct_id = line.payroll_id.struct_id
# 			employees.append([line.payroll_employee_id.id,line.payroll_employee_id.name+' '+line.payroll_employee_id.last_name])
# 			if line.payroll_employee_id.id not in employee_values:
# 				employee_values.update({line.payroll_employee_id.id:{}})
# 				employee_lines.update({line.payroll_employee_id.id:{}})
# 				is_edits.update({line.payroll_employee_id.id:{}})
# 				is_signs.update({line.payroll_employee_id.id:{}})
			
# 			for rule in line.rule_value_ids:
# 				if [rule.payroll_rule_id.id,rule.payroll_rule_id.name] not in rules:
# 					rules.append([rule.payroll_rule_id.id,rule.payroll_rule_id.name])
# 					decimals.update({rule.payroll_rule_id.id:rule.payroll_rule_id.decimal_point})
# 				if rule.payroll_rule_id.id not in employee_values[line.payroll_employee_id.id]:
					
# 					is_edits[line.payroll_employee_id.id].update({rule.payroll_rule_id.id:rule.is_edit})
# 					employee_lines[line.payroll_employee_id.id].update({rule.payroll_rule_id.id:rule.id})
# 					if rule.payroll_rule_id.id not in sum_rules:
# 						sum_rules.update({rule.payroll_rule_id.id:round(rule.value,2)})
# 					else:
# 						sum_rules[rule.payroll_rule_id.id] = sum_rules[rule.payroll_rule_id.id] +round(rule.value,2)
# 					if rule.payroll_rule_id.rulefield_type in ['risk_bonus','digit','bonus','salary_advance','from_previous_month','profit_bonus','monthly_bonus']:
# 						employee_values[line.payroll_employee_id.id].update({rule.payroll_rule_id.id:rule.value})
# 						is_signs[line.payroll_employee_id.id].update({rule.payroll_rule_id.id:True})
# 					else:
# 						employee_values[line.payroll_employee_id.id].update({rule.payroll_rule_id.id:rule.char_value})
# 						is_signs[line.payroll_employee_id.id].update({rule.payroll_rule_id.id:False})
# 		end = time.time()		
# 		_logger.info("\n\n\n\n\n LOGGER END TIME = '%s'"%(start-end))
# 		if struct_id:
# 			rules = []
# 			struct_line_ids = self.env['nomin.payroll.structure.line'].search([('struct_id','=',struct_id.id)],order='sequence asc')
# 			for struct in struct_line_ids:
# 				if struct.rule_id.show_in_payroll:
# 					if [struct.rule_id.id,struct.rule_id.name] not in rules:

# 						rules.append([struct.rule_id.id,struct.rule_id.name+' '+struct.rule_id.code])
# 		end = time.time()	
# 		_logger.info("\n\n\n\n\n LOGGER END TIME = '%s'"%(start-end))
# 		lines.update({'employees':employees,'rules':rules,'employee_values':employee_values,'employee_lines':employee_lines,'decimals':decimals,'is_signs':is_signs,'sum_rules':sum_rules,'is_edits':is_edits})
# 		return lines


		
# 					# CONNECTING TO LOYALTY SYSTEM

# class NominPayrollRuleValue(models.Model):
# 	_name = 'nomin.payroll.rule.value'
# 	_description = "Nomin payroll"
# 	_order = "create_date desc"

# 	line_id = fields.Many2one('nomin.payroll.line', string="Lines",ondelete='cascade',index=True)
# 	rulefield_type = fields.Selection([('digit','Digit'),('sign','Sign'),('salary_advance','Salary advance'),('risk_bonus','Bonus'),('bonus','Bonus'),('from_previous_month','Get from previous month'),('profit_bonus','profit bonus'),('monthly_bonus','monthly bonus')], string="Rule field type", default="digit")
# 	payroll_rule_id = fields.Many2one('nomin.payroll.rule', string="Rule", ondelete='restrict',index=True)
# 	value = fields.Float(string="Value",digits=(16,12),index=True)
# 	char_value = fields.Char(string="Value")
# 	sequence = fields.Integer(string="Value")
# 	is_edit = fields.Boolean(string="is_edit")
# 	is_edited = fields.Boolean(string="Is edited",default=False,index=True)
# 	attend = fields.Text(string="Formula",index=True)
# 	decimal_point = fields.Integer(string='Decimal point',index=True)
# 	show_in_payroll = fields.Boolean(string="Show in payroll Active",default=True,index=True)
# 	is_show = fields.Boolean(string="Is show" ,default=True,index=True)
# 	is_sum_view = fields.Boolean(string="Is sum view" ,default=False,index=True)
	
# 	#Ажилтаны мөр дээрх дүрмээс утга буцаах
	
# 	def get_rule_value(self,line,code):
# 		value = 0					
# 		for rule in line.rule_value_ids:
# 			if rule.payroll_rule_id.code == code:
# 				value =rule.value
# 		return value
# 	#Ажилтаны мөр дээрх  recursive function
	
# 	def action_recursive(self,python_code):
# 		rule_codes = re.findall('n\d+',python_code)
			
# 		for code in rule_codes:
# 			if len(code)==6:
# 				rule_id = self.env['nomin.payroll.rule'].search([('code','=',code)])
# 				if rule_id:					
# 					recode = str(rule_id.python_code)[7:]					
# 					python_code = python_code.replace(code,str(recode))
# 					python_code = self.action_recursive(python_code)
# 					python_code = python_code.replace(code,str(recode))		
# 		return python_code


# 	#Ажилтаны мөр дээрх дүрмийн кодыг хувиргах
	
# 	def convert_code(self,rule,rule_id,attend):		
# 		python_code = rule_id.python_code
# 		if rule.line_id.payroll_id.parent_id:
# 			rule_history = self.env['nomin.payroll.rule.history'].sudo().search([('month_id','=',rule.line_id.payroll_id.month_id.id),('rule_id','=',rule_id.id),('end_date','=',False)])
# 			if rule_history:
# 				python_code = rule_history.rule_id.python_code
# 		if python_code:
# 			if 'result' in python_code:			
# 				python_code = python_code[7:]
# 		if rule_id.value_type=='expression':
# 			rule_codes = re.findall('n\d+',python_code)		
# 			for code in rule_codes:
# 				if len(code)==6:
# 					rule_value_id = self.env['nomin.payroll.rule.value'].search([('payroll_rule_id.code','=',code),('line_id','=',rule.line_id.id)])					
# 					if rule_value_id:
# 						python_code = python_code.replace(code,str(rule_value_id.value))		
# 					else:
# 						python_code = python_code.replace(code,str(0))	
# 			if attend:
# 				attendlist = attend.split(',')
# 				attend = self.env[attendlist[0]].browse(int(attendlist[1]))
			
			
			
# 		try:
# 			return eval(python_code)
# 		except:			
# 			return False

# 	# 
	
# 	def get_from_previous_chosen_month(self, code, number, month_limit, field_name, depended_code = False):
# 		code = code.replace('nfunctions','n')
# 		offset = number - 1
# 		last_month = self.line_id.payroll_id.month_id.date_stop-relativedelta(months=month_limit)
# 		last_month_id = self.env['account.period'].search([('date_start','<=',last_month),('date_stop','>=',last_month)],limit = 1)
# 		where = ""
# 		where_offset = " OFFSET %s " % (offset)

# 		if self.payroll_rule_id.code in ('n36009','n36008','n36007','n36006','n36005','n36004','n36003','n36002','n36001',
# 						'n36034','n36033','n36032','n36028','n36027','n36026','n36025','n36024','n36023',
# 						'n36022','n36021','n36020','n36019','n36018','n36017'):	
# 			if not self.line_id.payroll_employee_id.employee_id:
# 				return False
# 			where += " AND value > 0 "
# 			if self.line_id.payroll_employee_id.employee_id.engagement_in_company:
# 				engagement_in_company = self.line_id.payroll_employee_id.employee_id.engagement_in_company.replace(day=1)
# 				engagement_in_company_str = engagement_in_company
# 				where += " AND H.date_start >= '%s' " % (engagement_in_company_str)
# 			query = """
# 				SELECT H.date_start FROM payroll_maternity_leave_line A 
# 					LEFT JOIN nomin_payroll_maternity_leave B ON A.leave_id=B.id
# 					INNER JOIN account_period H on B.month_id = H.id
# 				WHERE A.employee_id= %s AND B.leave_type='birth' and B.state in ('confirmed','closed') 
# 					AND H.date_start >= '%s' AND H.date_start < '%s' 
# 				ORDER BY H.date_start desc LIMIT 1
# 			""" % (self.line_id.payroll_employee_id.employee_id.id, last_month_id.date_start, self.line_id.payroll_id.month_id.date_start)
# 			dictfetchall=self.env.cr.dictfetchall()
# 			if dictfetchall:
# 				for dic in dictfetchall:
# 					maternity_date_txt = dic['date_start']
# 					maternity_date = maternity_date_txt+relativedelta(months=1)
# 					where += " AND H.date_start >= '%s' " % (maternity_date)
# 		if last_month_id:
# 			if depended_code:
# 				month = self.get_from_previous_chosen_month(depended_code, number, month_limit, 'month')
# 				where = " and H.date_start = '%s'" % (month) if month else where
# 				where_offset = "" if month else where_offset

# 			query = """
# 				SELECT C.value as "value", H.date_start as "month"
# 					FROM nomin_payroll A inner join nomin_payroll_line B ON A.id= B.payroll_id 
# 					INNER JOIN account_period H ON A.month_id = H.id
# 					INNER JOIN nomin_payroll_rule_value C ON B.id=C.line_id
# 					INNER JOIN nomin_payroll_rule D ON D.id=C.payroll_rule_id
# 					INNER JOIN nomin_payroll_employee G ON G.id=B.payroll_employee_id
# 				WHERE A.struct_type = 'salary_late' AND A.state in ('confirmed','closed') 
# 					AND G.id = %s and D.code in ('%s') 
# 					AND H.date_start >= '%s' AND H.date_start < '%s' 
# 					%s
# 				ORDER BY H.date_start DESC
# 				%s LIMIT 1
# 			""" % (self.line_id.payroll_employee_id.id, code, last_month_id.date_start, self.line_id.payroll_id.month_id.date_start, where, where_offset)
# 			self.env.cr.execute(query)
# 			fetchall = self.env.cr.dictfetchall()
# 			if fetchall and fetchall:
# 				for fetch in fetchall:
# 					if fetch and fetch[field_name]:
# 						return fetch[field_name]
# 		return False

# 	# Ажилтаны мөр дээрх утга дээр өөрчлөлт оруулахад хадгалах
# 	@api.model
# 	def set_value(self,get_id, value):	
# 		value = float(value)		
# 		print("\n\n =======value=========",value,get_id)	
# 		for rule in self.browse(get_id):
# 			if rule.payroll_rule_id.code=='n31005' and value>0:											
# 				employee_id = rule.line_id.payroll_employee_id.employee_id				
# 				if employee_id.job_id:
# 					if employee_id.job_id.below_than_stockkeeper and value >60:
# 						value = 60
# 					elif not employee_id.job_id.below_than_stockkeeper and value >30:
# 						self.env.cr.execute("SELECT COUNT(*) FROM generate_series(timestamp %s, %s, '1 day') AS g(mydate) WHERE EXTRACT(DOW FROM mydate) = 6",(rule.line_id.payroll_id.month_id.date_start,rule.line_id.payroll_id.month_id.date_stop))
# 						count_saturdays = self.env.cr.fetchone()[0]
# 						if count_saturdays>4:
# 							if value>20:
# 								value = 20
# 						else:
# 							value = 30
				
# 					# if float(value) >float(rule.value):
# 					# 	value = rule.value
# 			rule.write({'value':value,'is_edited':True})
# 		for rule in self.browse(get_id):
# 			rule.line_id.action_computebyQUERY()
			
# 		return { 'type' :  'ir.actions.act_close_wizard_and_reload_view' }




# class NominPayrollHistory(models.Model):
# 	_inherit = 'request.history'

# 	payroll_id = fields.Many2one('nomin.payroll', string='Payroll', ondelete="cascade")

# class PayrollPaymentHistory(models.Model):
# 	_name = 'payroll.payment.history'
# 	_order = 'create_date desc'
# 	payment_request_id = fields.Many2one('payment.request',string="Payment request")
# 	move_id = fields.Many2one('account.move', string="Move")
# 	payroll_id = fields.Many2one('nomin.payroll', string="Payroll")


# class MillionaireNesHistory(models.Model):
# 	_name = 'millionaire.nes.history'
# 	_order = 'create_date desc'
# 	payroll_id = fields.Many2one('nomin.payroll', string="Payroll")
# 	nes_number = fields.Char(string="NES дугаар")
# 	employee_id = fields.Many2one('hr.employee', string="Ажилтан")
# 	amount = fields.Float(string="Дүн")