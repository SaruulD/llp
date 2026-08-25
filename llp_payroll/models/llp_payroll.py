# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
import logging
import re
_logger = logging.getLogger(__name__)
from operator import itemgetter
from odoo.tools.safe_eval import safe_eval # type: ignore
import base64

class LLPPayroll(models.Model):
    _name = 'llp.payroll'
    _inherit = ['mail.thread']
    _description = "LLP payroll"
    _order = "create_date desc"

    def _model_id_domain(self):
        model = self.env['ir.model']._get(self._name)
        return [('model_id', '=', model.id)]

    name = fields.Char(string='Code',tracking=True, readonly=True)
    start_date = fields.Date(string="Start Date", required=True, tracking=True)
    end_date = fields.Date(string="End Date", required=True, tracking=True)
    # dynamic_workflow_id = fields.Many2one(
    #     'dynamic.workflow',
    #     string="Dynamic workflow",
    #     domain=_model_id_domain,
    # )

    company_id = fields.Many2one('res.company', string="Company",default=lambda self: self.env.company,)
	
    department_id = fields.Many2many('hr.department',string="Department",tracking=True,
        domain="['|', ('company_id', '=', company_id), ('company_id', '=', False)]")
    struct_id = fields.Many2one('llp.payroll.structure',string="Stucture", domain="[('state','=','done')]",tracking=True)
    line_ids = fields.One2many('llp.payroll.line','payroll_id',string="Lines")
    state = fields.Selection([
        ('draft','Draft'),
        ('sent','Sent'),
        ('pending','Pending'),
        ('verify','Verify'),
        ('confirmed','Confirmed'),
        ('done','Done'),
        ('closed','Closed')
    ],string='State',default='draft',tracking=True)
    history_ids = fields.One2many('request.history','payroll_id',string="State History")
    payment_history_ids = fields.One2many('payroll.payment.history', 'payroll_id', string="Payment history")

    

    def send_mail_to_employees(self):
        self._send_payroll_rule_mail()
 
    def _send_payroll_rule_mail(self):
        self.ensure_one()
 
        # Тухайн payroll-ийн struct-д хамаарах, send_mail=True рулиудыг
        # structure дэх дараалал (sequence)-аар нь авна
        struct_lines = self.struct_id.line_ids.filtered(
            lambda l: l.rule_id.send_mail
        ).sorted(key=lambda l: l.sequence)
 
        if not struct_lines:
            return
 
        for line in self.line_ids:
            employee = line.employee_id
 
            if not employee.work_email:
                continue
 
            values = []
 
            for struct_line in struct_lines:
                rule = struct_line.rule_id
 
                rule_value = line.rule_value_ids.filtered(
                    lambda r: r.payroll_rule_id == rule
                )
 
                if not rule_value:
                    continue
 
                # sign төрлийн утга char_value дотор, бусад нь value дотор хадгалагдана
                if rule_value.rulefield_type == 'sign':
                    val = rule_value.char_value
                else:
                    val = rule_value.value
 
                values.append({
                    'name': rule.name,
                    'code': rule.code,
                    'value': val,
                    'need_highlight': rule.need_highlight,
                })
 
            if not values:
                continue
 
            self._send_employee_mail(employee, values)
 
 
    def _send_employee_mail(self, employee, values):
        self.ensure_one()
 
        # PDF/attachment үүсгэхгүй, задаргааг зөвхөн мэйлийн body дотор
        # (mail_template_payroll-ийн body_html) шууд харуулна. employee_id /
        # employee_values-ийг context-оор дамжуулснаар body_html доторх
        # doc._get_employee_header_html(...) / doc._get_employee_report_html(...)
        # тухайн ажилтны өөрийнх нь мэдээллийг зурна.
        template = self.env.ref('llp_payroll.mail_template_payroll')  # module нэрээ тохируулна
        template.with_context(
            employee_id=employee.id,
            employee_values=values,
        ).send_mail(
            self.id,
            force_send=True,
            email_values={
                'email_to': employee.work_email,
            },
        )
 
 
    def _get_employee_header_html(self, employee):
        """Ажилтны нэр / хэлтэс / регистрийн дугаар / албан тушаалыг
        xlsx загварын A5:D6 layout-той адил 2 мөр, 4 баганаар харуулна.
        Ашиглалт: report/mail template дотор
        `t-raw="doc._get_employee_header_html(employee)"`.
        """
        label = "padding: 4px 8px; font-size: 12pt; font-family: 'Arial'; font-weight: bold;"
        value = "padding: 4px 8px; font-size: 12pt; font-family: 'Arial';"
 
        return """
            <table style="border: 1px solid black; border-collapse: collapse;" width="100%%">
                <tr>
                    <td style="%s" width="20%%">Ажилтны нэр</td>
                    <td style="%s" width="30%%">%s</td>
                    <td style="%s" width="20%%">Газар, хэлтэс</td>
                    <td style="%s" width="30%%">%s</td>
                </tr>
                <tr>
                    <td style="%s">Регистрийн дугаар</td>
                    <td style="%s">%s</td>
                    <td style="%s">Албан тушаал</td>
                    <td style="%s">%s</td>
                </tr>
            </table>
        """ % (
            label, value, employee.name or '',
            label, value, employee.department_id.name or '',
            label, value, employee.identification_id or '',
            label, value, employee.job_id.name or '',
        )
  
    def _get_employee_report_html(self, values):
        """`values` жагсаалт (`_send_payroll_rule_mail`-с ирнэ, [{'name','code','value'}, ...])-ыг
        Код | Нэр | Дүн гэсэн бүрэн хүрээтэй (bordered) хүснэгт болгоно.
        Захын 2 багана (зүүн/баруун 10%) хүрээгүй, зөвхөн хоосон зай тул
        доторх хүрээтэй хүснэгт хуудасны голд харагдана. QWeb report/mail
        template дотор `t-raw="doc._get_employee_report_html(...)"` байдлаар
        дуудна.
        """
        cell = "border: 1px solid black; border-collapse: collapse; padding: 4px 8px; font-size: 11pt; font-family: 'Arial';"
        head = cell + "background-color: #333369; color: white; font-weight: bold; text-align: center;"
 
        inner = """
            <table style="border: 1px solid black; border-collapse: collapse;" width="100%%">
                <tr>
                    <td style="%s" width="15%%">Код</td>
                    <td style="%s" width="55%%">Нэр</td>
                    <td style="%s" width="30%%">Дүн</td>
                </tr>
        """ % (head, head, head)
 
        highlight = cell + "background-color: #A8ECFF;"  # тодруулах мөрийн өнгө
 
        for val in values or []:
            amount = val.get('value')
            if isinstance(amount, (int, float)):
                amount_display = '{:,.2f}'.format(amount)
            else:
                amount_display = amount or ''
 
            row_style = highlight if val.get('need_highlight') else cell
 
            inner += """
                <tr>
                    <td style="%s text-align: center;">%s</td>
                    <td style="%s text-align: left;">%s</td>
                    <td style="%s text-align: right;">%s</td>
                </tr>
            """ % (
                row_style, val.get('code') or '',
                row_style, val.get('name') or '',
                row_style, amount_display,
            )
 
        inner += "</table>"
 
        # Гаднах хүснэгт хүрээгүй (spacer); зүүн/баруун 10% хоосон,
        # дунд 80%-д дээрх хүрээтэй хүснэгтийг байрлуулна.
        return """
            <table width="100%%" style="border-collapse: collapse; margin-top: 8px;">
                <tr>
                    <td width="10%%"></td>
                    <td width="80%%">%s</td>
                    <td width="10%%"></td>
                </tr>
            </table>
        """ % inner

    
    def get_company_logo_mail(self, ids):
        """Мэйлийн body_html-д зориулсан лого.
        `get_company_logo_*`-ийн base64 `data:` URI-г Outlook зэрэг
        зарим мэйл клиент дэмждэггүй тул (зураг ачаалахгүй, зөвхөн
        alt текст нь харагдана) үүний оронд Odoo-ийн стандарт
        `/web/image/res.company/<id>/logo` URL ашиглана.
 
        АНХААРАХ: 'web.base.url' систем параметр (Тохиргоо > Техникийн
        > Системийн параметрүүд) нь гадна талаас (хүлээн авагчийн
        мэйл клиентээс) хүрэх боломжтой жинхэнэ домэйн/IP байх ёстой,
        localhost биш.
        """
        report_id = self.browse(ids).exists()
        if not report_id or not report_id.company_id or not report_id.company_id.logo:
            return ''
 
        company = report_id.company_id
        base_url = report_id.get_base_url()
 
        return (
            '<img alt="%s" width="300" src="%s/web/image/res.company/%s/logo" />'
        ) % (company.name or '', base_url, company.id)
 
 
    def get_company_logo_small(self, ids):
        report_id = self.browse(ids)
        image_buf = report_id.company_id.logo_web.decode('utf-8')
        image_str = ''
        if len(image_buf)>10:
            image_str = '<img alt="Embedded Image" width="128" src="data:image/png;base64,%s" />'%(image_buf)
        return image_str
    def get_company_logo_medium(self, ids):
        report_id = self.browse(ids).exists()

        if not report_id:
            return ''
        logo = report_id.company_id.logo_web
        if not logo:
            return ''

        image_buf = logo.decode('utf-8') if isinstance(logo, bytes) else logo

        return (
            '<img alt="Embedded Image" width="300" '
            'src="data:image/png;base64,%s" />'
        ) % image_buf
    def get_company_logo_big(self, ids):
        report_id = self.browse(ids).exists()

        if not report_id or not report_id.company_id:
            return ''

        logo = report_id.company_id.logo_web
        if not logo:
            return ''

        # Odoo binary field нь ихэнхдээ base64 bytes/string хэлбэртэй ирдэг
        image_buf = logo.decode('utf-8') if isinstance(logo, bytes) else logo

        return (
            '<img alt="Company Logo" width="1024" '
            'src="data:image/png;base64,%s" />'
        ) % image_buf
        
    
 

    @api.model
    def create(self, vals):
        seq_code = 'llp.payroll.seq'
        if not self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1):
            self.env['ir.sequence'].sudo().create({
                'name': 'LLP Payroll Sequence',
                'code': seq_code,
                'prefix': 'PA/%(year)s/',
                'padding': 4,
                'number_next': 1,
                'number_increment': 1,
            })

        vals['name'] = self.env['ir.sequence'].next_by_code(seq_code) or '/'

        result = super(LLPPayroll, self).create(vals)
        return result
    
    def action_send(self):
        if not self.line_ids:
            raise UserError((u'Ажилтнуудын мэдээлэл алга байна.'))
        self.write({'state':'sent'})
        self.create_history('sent')
        
    def action_approve(self):
        self.write({'state':'pending'})
        self.create_history('pending')

    def action_verify(self):
        self.write({'state':'verify'})
        self.create_history('verify')

    def action_return(self):
        self.write({'state':'draft'})
        self.create_history('draft')

    # def action_confirm(self):
    #     self.write({'state':'confirmed'})
    #     self.create_history('confirmed')
    # def action_confirm(self):
    #     for payroll in self:
    #         payroll.write({'state': 'confirmed'})
    #         payroll.create_history('confirmed')

    #         for line in payroll.line_ids:
    #             # debt rule ашигласан эсэх
    #             if not line.rule_value_ids.filtered('is_debt_rule'):
    #                 continue

    #             loan_lines = self.env['llp.payroll.employee.debt.line'].search([
    #                 ('employee_id', '=', line.employee_id.id),
    #                 ('state', '=', 'waiting_approval_1'),
    #             ])

    #             loan_lines.write({
    #                 'state': 'approve',
    #                 'done_or_not': True
    #             })
    def action_confirm(self):
        for payroll in self:
            # payroll.write({'state': 'confirmed'})
            # payroll.create_history('confirmed')

            for line in payroll.line_ids:
                has_debt_rule = bool(line.rule_value_ids.filtered('is_debt_rule'))
                has_vacation_rule = bool(line.rule_value_ids.filtered('is_vacation_rule'))

                if not has_debt_rule and not has_vacation_rule:
                    continue

                # --- DEBT тал ---
                if has_debt_rule:
                    debt_lines = self.env['llp.payroll.employee.debt.line'].search([
                        ('employee_id', '=', line.employee_id.id),
                        ('debt_id.state', '=', 'done'),
                        ('debt_id.struct_type', '=', payroll.struct_id.struct_type),
                        ('debt_id.month', '>=', payroll.start_date),
                        ('debt_id.month', '<=', payroll.end_date),
                    ])

                    if debt_lines:
                        debt_lines.write({'done_or_not': True})

                        debts = debt_lines.mapped('debt_id')
                        for debt in debts:
                            if debt.line_ids and all(debt.line_ids.mapped('done_or_not')):
                                debt.write({'state': 'closed'})

                # --- VACATION тал ---
                if has_vacation_rule:
                    vacation_lines = self.env['llp.payroll.employee.vacation.line'].search([
                        ('employee_id', '=', line.employee_id.id),
                        ('vacation_id.state', '=', 'done'),
                        ('vacation_id.struct_type', '=', payroll.struct_id.struct_type),
                        ('vacation_id.month', '>=', payroll.start_date),
                        ('vacation_id.month', '<=', payroll.end_date),
                    ])

                    if vacation_lines:
                        vacation_lines.write({'done_or_not': True})

                        vacations = vacation_lines.mapped('vacation_id')
                        for vacation in vacations:
                            if vacation.line_ids and all(vacation.line_ids.mapped('done_or_not')):
                                vacation.write({'state': 'locked'})
                                
                                employees = vacation.line_ids.mapped('employee_id')
                                if vacation.month:
                                    employees.write({'last_vacation_salary_date': vacation.month})



    def action_payment_request(self):
        self.ensure_one()
        action = self.env.ref('llp_payroll.action_llp_payroll_payment_request').read()[0]
        return action
    

    def action_account_move(self):
        action = self.env["ir.actions.actions"]._for_xml_id("llp_payroll.action_llp_payroll_account_move")
        return action
    
    # def action_get_data(self):
    #     rules = []
    #     lines= []
    #     for pay in self:
    #         employee_ids = self.env['hr.employee'].search([('department_id','=',pay.department_ids.ids),('active','=',True)])

    #         if not pay.line_ids:
    #             for line in pay.struct_id.line_ids:
    #                 is_edit =False
    #                 if line.rule_id.ruleview_type=='edit':
    #                     is_edit = True
    #                 rules.append((0,0,{'payroll_rule_id':line.rule_id.id,
    #                                    'show_in_payroll':line.rule_id.show_in_payroll,
    #                                    'decimal_point':line.rule_id.decimal_point,
    #                                    'rulefield_type':line.rule_id.rulefield_type,
    #                                    'sequence':line.sequence,
    #                                    'value':0,
    #                                    'is_edit':is_edit}))
    #             for employee_id in employee_ids:
    #                 lines.append((0,0,{'rule_value_ids':rules,'employee_id':employee_id.id}))
    #             if lines:
    #                 pay.write({'line_ids':lines})

    #         self.action_computebyQUERY()
    #     return {'type': 'ir.actions.client', 'tag': 'reload'}


    # def action_get_data(self):
    #     for pay in self:
    #         employee_ids = self.env['hr.employee'].search([
    #             ('department_id', 'in', pay.department_id.ids),
    #             ('active', '=', True)
    #         ])

    #         if not pay.line_ids:
    #             lines = []
    #             number = 1

    #             for employee in employee_ids:
    #                 rules = []

    #                 for line in pay.struct_id.line_ids:
    #                     is_edit = line.rule_id.ruleview_type == 'edit'

    #                     rules.append((0, 0, {
    #                         'payroll_rule_id': line.rule_id.id,
    #                         'show_in_payroll': line.rule_id.show_in_payroll,
    #                         'decimal_point': line.rule_id.decimal_point,
    #                         'rulefield_type': line.rule_id.rulefield_type,
    #                         'sequence': line.sequence,
    #                         'value': 0,
    #                         'is_edit': is_edit,
    #                     }))

    #                 lines.append((0, 0, {
    #                     'number': number,
    #                     'rule_value_ids': rules,
    #                     'employee_id': employee.id,
    #                 }))

    #                 number += 1

    #             if lines:
    #                 pay.write({'line_ids': lines})

    #         pay.action_computebyQUERY()

    #     return {'type': 'ir.actions.client', 'tag': 'reload'}


    def action_get_data(self):
        for pay in self:
            emp_domain = [('active', '=', True)]
 
            # Хэлтэс сонгосон бол зөвхөн тэдгээр хэлтсийн ажилтныг,
            # сонгоогүй бол тухайн компанийн бүх ажилтныг авна.
            if pay.department_id:
                emp_domain.append(('department_id', 'in', pay.department_id.ids))
 
            if pay.company_id:
                emp_domain.append(('company_id', '=', pay.company_id.id))

            contracts = self.env['hr.contract'].search([
                ('employee_id', '!=', False),
                ('date_start', '<=', pay.end_date),
                ('state', 'in', ['open','close']),
                '|',
                    ('date_end', '=', False),
                    ('date_end', '>=', pay.start_date),
                    ('state', 'in', ['open','close']),
            ])
            emp_domain.append(('id', 'in', contracts.employee_id.ids))

            employee_ids = self.env['hr.employee'].search(emp_domain)
 
            # Дахин татахад өмнөх мөрүүд (болон cascade-аар устах
            # rule_value_ids)-ийг устгаад, шинээр татсан мэдээллээр
            # дахин үүсгэнэ.
            pay.line_ids.unlink()
 
            lines = []
            number = 1
 
            for employee in employee_ids:
                    rules = []

                    for line in pay.struct_id.line_ids:
                        is_edit = line.rule_id.ruleview_type == 'edit'
                        python_code = line.rule_id.python_code or ''

                        is_debt_rule = (
                            line.rule_id.object_type == 'debt'
                            and any(
                                x in python_code
                                for x in (
                                    'object.sum_total',
                                    'object.withholding_amount',
                                    'object.sum_loan_amount',
                                )
                            )
                        )

                        is_vacation_rule = (
                            line.rule_id.object_type == 'vacation'
                            and any(
                                x in python_code
                                for x in (
                                    'object.total_vacation_amount',
                                )
                            )
                        )

                        rules.append((0, 0, {
                            'payroll_rule_id': line.rule_id.id,
                            'show_in_payroll': line.rule_id.show_in_payroll,
                            'decimal_point': line.rule_id.decimal_point,
                            'rulefield_type': line.rule_id.rulefield_type,
                            'sequence': line.sequence,
                            'value': 0,
                            'is_edit': is_edit,
                            'is_debt_rule': is_debt_rule,
                            'is_vacation_rule': is_vacation_rule,
                        }))

                    lines.append((0, 0, {
                        'number': number,
                        'rule_value_ids': rules,
                        'employee_id': employee.id,
                    }))

                    number += 1
 
            if lines:
                pay.write({'line_ids': lines})
 
            pay.action_computebyQUERY()
 
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    
    def action_compute(self):
        for pay in self:
            if not pay.line_ids:
                raise UserError(_(
                    'Ажилтны мэдээлэл ачаалагдаагүй байна. '
                    'Эхлээд "Get Data" товчийг дарна уу.'
                ))
            pay.action_computebyQUERY()

        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
 
    def action_computebyQUERY(self):
        query = "select C.id as rule_value_id,D.rule_type as rule_type, D.rulefield_type as rulefield_type, D.object_type as object_type, \
                    G.id as employee , D.ruleview_type as ruleview_type, D.code as code, D.name as rule_name, D.regular_number as regular_number, B.id as line_id, D.python_code as python_code, F.exp_sequence as exp_sequence, C.is_edited as is_edited\
                    from llp_payroll A inner join llp_payroll_line B ON A.id= B.payroll_id \
                        inner join llp_payroll_rule_value C on B.id=C.line_id \
                        inner join llp_payroll_rule D on D.id=C.payroll_rule_id \
                        inner join llp_payroll_structure E ON E.id= A.struct_id \
                        inner join llp_payroll_structure_line F ON F.struct_id= E.id and F.rule_id=D.id\
                        inner join hr_employee G ON G.id=B.employee_id \
                where A.id=%s \
                group by rule_value_id, rule_type, D.rulefield_type, object_type, employee, ruleview_type, code, D.name, B.id,\
                    python_code, regular_number, exp_sequence, is_edited \
                order by F.exp_sequence asc "%(self.id)
        self.env.cr.execute(query)
        dictfetchall = self.env.cr.dictfetchall()

        formulas = {}
        if dictfetchall:
            for dic in dictfetchall:
                group = dic['exp_sequence']
                if group not in formulas:
                    formulas[group] = {'exp_sequence': 0, 'rules': {}}
                formulas[group]['exp_sequence'] = group
                group1 = dic['code']
                if group1 not in formulas[group]['rules']:
                    formulas[group]['rules'][group1] = {
                        'code': '', 'name': '', 'python_code': '', 'rule_type': '',
                        'object_type': '', 'rulefield_type': '', 'employees': {}
                    }
                formulas[group]['rules'][group1]['code'] = group1
                formulas[group]['rules'][group1]['name'] = dic.get('rule_name') or ''
                formulas[group]['rules'][group1]['python_code'] = dic['python_code']
                formulas[group]['rules'][group1]['regular_number'] = dic['regular_number']
                formulas[group]['rules'][group1]['rule_type'] = dic['rule_type']
                formulas[group]['rules'][group1]['object_type'] = dic['object_type']
                formulas[group]['rules'][group1]['rulefield_type'] = dic['rulefield_type']
                group2 = dic['employee']
                if group2 not in formulas[group]['rules'][group1]['employees']:
                    formulas[group]['rules'][group1]['employees'][group2] = {
                        'employee': 0, 'rule_value_id': 0, 'line_id': 0, 'is_edited': False,
                    }
                formulas[group]['rules'][group1]['employees'][group2]['employee'] = dic['employee']
                formulas[group]['rules'][group1]['employees'][group2]['rule_value_id'] = dic['rule_value_id']
                formulas[group]['rules'][group1]['employees'][group2]['line_id'] = dic['line_id']
                formulas[group]['rules'][group1]['employees'][group2]['is_edited'] = dic['is_edited']

        # ★ Алдааг цуглуулах жагсаалт
        errors_by_rule = {}  # {rule_code: {'error': str, 'python_code': str, 'count': int}} 
        employee_errors = []

        if formulas:
            object_type_base_map = self.env['llp.payroll.rule']._get_object_type_base_map()
            for formula in sorted(formulas.values(), key=itemgetter('exp_sequence')):
                for ruled in sorted(formula['rules'].values(), key=itemgetter('code')):
                    for emp in sorted(ruled['employees'].values(), key=itemgetter('employee')):
                        value = None
                        rule = False
                        if emp['rule_value_id']:
                            rule = self.env['llp.payroll.rule.value'].browse(emp['rule_value_id'])

                        if ruled['rule_type'] == 'code':
                            # ★ Энэ ажилтан/дүрэм дээрх бүх SQL/eval-ийг savepoint дотор хийнэ.
                            #   Алдаа гарвал зөвхөн энэ хэсэг rollback хийгдэж, гаднах
                            #   transaction нь эвдрэлгүй үргэлжилнэ (InFailedSqlTransaction-оос сэргийлнэ).
                            try:
                                with self.env.cr.savepoint():
                                    value = 0
                                    python_code = ruled['python_code']
                                    object = {}
                                    object_base_type = object_type_base_map.get(ruled['object_type'], ruled['object_type'])

                                    if object_base_type == 'contract':
                                        object = self.env['hr.contract'].search([
                                                ('employee_id', '=', emp['employee']),
                                                ('date_start', '<=', self.end_date),
                                                '|',
                                                    ('date_end', '=', False),
                                                    ('date_end', '>=', self.start_date),
                                            ], limit=1)
                                    elif object_base_type == 'vacation':
                                        self.env.cr.execute(
                                            "select B.id from llp_payroll_employee_vacation A "
                                            "inner join llp_payroll_employee_vacation_line B ON A.id=B.vacation_id "
                                            "where A.state = 'done' and B.employee_id = %s and A.month BETWEEN %s AND %s and A.struct_type=%s",
                                            (emp['employee'], self.start_date, self.end_date, self.struct_id.struct_type)
                                        )
                                        fetch = self.env.cr.fetchone()
                                        if fetch and fetch[0]:
                                            object = self.env['llp.payroll.employee.vacation.line'].browse(fetch[0])

                                    elif object_base_type == 'employee':
                                        object = self.env['hr.employee'].browse(emp['employee'])

                                    elif object_base_type == 'debt':
                                        self.env.cr.execute(
                                            "select A.id from llp_payroll_employee_debt_line A "
                                            "inner join llp_payroll_employee_debt B ON A.debt_id=B.id "
                                            "where B.month BETWEEN %s AND %s and A.employee_id=%s "
                                            "and B.struct_type=%s and B.state in ('done')",
                                            (self.start_date, self.end_date, emp['employee'], self.struct_id.struct_type)
                                        )
                                        fetch = self.env.cr.fetchone()
                                        if fetch and fetch[0]:
                                            object = self.env['llp.payroll.employee.debt.line'].sudo().browse(fetch[0])

                                    elif object_base_type == 'attendance':
                                        object = {}
                                        query = "select tbl.id from time_balance tb \
                                            inner join time_balance_line tbl ON tb.id=tbl.balance_id \
                                            where tb.state = 'accountant' and tbl.employee_id = %s and tb.date_from<='%s' \
                                            AND tb.date_to>='%s'"%(emp['employee'],self.start_date, self.end_date,)
                                        self.env.cr.execute(query)
                                        fetch = self.env.cr.fetchone()
                                        if fetch and fetch[0]:
                                            object = self.env['time.balance.line'].browse(fetch[0])
                                    elif object_base_type == 'kpi':
                                        object = {}
                                    elif ruled['object_type'] == 'employee':
                                        object = self.env['hr.employee'].browse(emp['employee'])

                                    # ★ underscore-той код (жишээ нь OZ_E)-ийг таних болгож regex-ийг сайжруулав
                                    rule_codes = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', str(python_code))

                                    if rule_codes:
                                        # ★ Зөвхөн одоогийн structure-д ашиглагдаж буй rule-ийн
                                        #    code-уудыг л орлуулна (өөр structure-ийн ижил
                                        #    нэртэй rule-ийн утга орж ирэхээс сэргийлнэ)
                                        where = "where A.line_id = %s and F2.struct_id = %s " % (
                                            emp['line_id'], self.struct_id.id
                                        )
                                        if len(rule_codes) > 1:
                                            where += " and B.code in %s" % (str(tuple(rule_codes)))
                                        else:
                                            where += " and B.code = '%s'" % (str(rule_codes[0]))

                                        query = """
                                            select A.value as value, A.char_value as char_value,
                                                   B.code as code, B.rulefield_type as rulefield_type
                                            from llp_payroll_rule_value A
                                            inner join llp_payroll_rule B ON A.payroll_rule_id = B.id
                                            inner join llp_payroll_structure_line F2 ON F2.rule_id = B.id
                                        """ + where

                                        self.env.cr.execute(query)
                                        fetchedAll = self.env.cr.dictfetchall()

                                        if fetchedAll:
                                            # ★ Урт кодыг эхэлж орлуулна (жиш: OZ_E, OZ хоёул байвал
                                            #    OZ-г эхэлж орлуулбал OZ_E эвдэрнэ)
                                            for fetched in sorted(fetchedAll, key=lambda x: len(x['code']), reverse=True):
                                                if fetched['rulefield_type'] == 'sign':
                                                    python_code = python_code.replace(fetched['code'], repr(fetched['char_value'] or ''))
                                                else:
                                                    python_code = python_code.replace(fetched['code'], str(fetched['value'] if fetched['value'] is not None else 0))

                                            rule_codes2 = re.findall(r'n\d+', str(python_code))
                                            if rule_codes2:
                                                for code in rule_codes2:
                                                    python_code = python_code.replace(code, str(0))

                                    if ruled['rulefield_type'] == 'from_previous_payroll':
                                        try:
                                            value = self.get_from_previous_payroll(emp['employee'], python_code, self.start_date, self.end_date)
                                            if value is None:
                                                value = 0
                                        except Exception as e_prev:
                                            # ★ Попап дээр огт харуулахгүй — зөвхөн log
                                            _logger.info(
                                                "Payroll: from_previous_payroll error (харуулахгүй) - rule: %s, employee: %s, error: %s",
                                                ruled['code'], emp['employee'], e_prev
                                            )
                                            value = 0

                                        # ★ Амжилттай эсэхээс үл хамааран (0 ч бай, бодит
                                        #   утга ч бай) DB рүү нэг л удаа бичнэ.
                                        if emp['is_edited'] == False:
                                            self.env.cr.execute(
                                                "update llp_payroll_rule_value set value=%s where id=%s",
                                                (value, emp['rule_value_id'])
                                            )

                                    else:
                                        # ★ Зөвхөн 'from_previous_payroll' биш дүрмүүд л
                                        #   safe_eval/eval-ээр тооцоологдоно. Эсрэг тохиолдолд
                                        #   дээрх get_from_previous_payroll-ийн python_code
                                        #   (жишээ нь зүгээр л 'SA1' гэсэн нэр) энд дахин
                                        #   eval хийгдэж NameError өгдөг байсныг засав.
                                        if rule:
                                            local_dict = {
                                                'rule': rule,
                                                'object': object,
                                                'payroll_start_date': self.start_date,
                                                'payroll_end_date': self.end_date,
                                            }
                                            safe_eval(python_code, local_dict, mode="exec", nocopy=True)
                                            value = local_dict.get('result')
                                        else:
                                            value = eval(python_code)

                                        if isinstance(value, (tuple, list)):
                                            raise UserError(_(
                                                "Томьёо tuple/list утга буцаалаа: %r"
                                            ) % (value,))

                                        if ruled['rulefield_type'] == 'digit':
                                            if not value:
                                                value = 0
                                            if emp['is_edited'] == False:
                                                self.env.cr.execute(
                                                    'update llp_payroll_rule_value set value = %s where id = %s',
                                                    (value, emp['rule_value_id'])
                                                )
                                        elif ruled['rulefield_type'] == 'sign':
                                            if emp['is_edited'] == False:
                                                self.env.cr.execute(
                                                    "update llp_payroll_rule_value set char_value = %s where id = %s",
                                                    (value if value is not None else False, emp['rule_value_id'])
                                                )
                            except Exception as e:
                                if isinstance(e, ZeroDivisionError):
                                    # ★ Хуваагч тухайн ажилтан дээр 0 байх нь хэвийн
                                    #   тохиолдол. Алдаа биш тул хэрэглэгчид огт
                                    #   харуулахгүй, зөвхөн log-д тэмдэглээд өнгөрнө.
                                    _logger.info(
                                        "Payroll: zero division (хэвийн, харуулахгүй) - rule: %s, employee: %s",
                                        ruled['code'], emp['employee']
                                    )

                                elif object_type_base_map.get(ruled['object_type'], ruled['object_type']) in ('attendance', 'vacation', 'debt'):
                                    # ★ 'attendance'/'vacation'/'debt' төрлийн дүрэгт
                                    #   тухайн ажилтанд харгалзах бичлэг (цагийн
                                    #   бүртгэл, амралт, зээл) олдоогүй үед object
                                    #   нь хоосон dict ({}) болдог тул object.xxx
                                    #   хандалт хийхэд AttributeError гэх мэт алдаа
                                    #   гарах нь хэвийн тохиолдол. Попап дээр огт
                                    #   харуулахгүй, зөвхөн log-д тэмдэглэнэ.
                                    _logger.info(
                                        "Payroll: %s object error (хэвийн, харуулахгүй) - rule: %s, employee: %s, error: %s",
                                        object_type_base_map.get(ruled['object_type'], ruled['object_type']),
                                        ruled['code'], emp['employee'], e
                                    )

                                elif isinstance(e, (NameError, SyntaxError, TypeError, UserError)):
                                    if ruled['code'] not in errors_by_rule:
                                        errors_by_rule[ruled['code']] = {
                                            'error': str(e),
                                            'python_code': ruled['python_code'],
                                            'name': ruled.get('name') or '',
                                        }
                                    _logger.error(
                                        "Payroll compute error (rule)\n"
                                        "  Дүрэм: %s\n"
                                        "  Ажилтан: %s\n"
                                        "  Алдаа: %s\n"
                                        "  Томьёо: %s",
                                        ruled['code'], emp['employee'], e, ruled['python_code']
                                    )

                                else:
                                    # ★ Бусад алдаа (AttributeError, KeyError, ValueError
                                    #   гэх мэт) — ихэвчлэн тухайн ажилтны өгөгдөл
                                    #   дутуу/буруутай холбоотой (жишээ нь холбогдох
                                    #   contract/insurance гэх мэт record олдоогүй),
                                    #   тиймээс ажилтнаар тусад нь харуулна.
                                    try:
                                        emp_rec = self.env['hr.employee'].browse(emp['employee'])
                                        emp_name = emp_rec.name or ('ID %s' % emp['employee'])
                                    except Exception:
                                        emp_name = 'ID %s' % emp['employee']

                                    employee_errors.append({
                                        'rule': ruled['code'],
                                        'rule_name': ruled.get('name') or '',
                                        'employee': emp_name,
                                        'error': str(e),
                                        'python_code': ruled['python_code'],
                                    })
                                    _logger.error(
                                        "Payroll compute error (employee)\n"
                                        "  Дүрэм: %s\n"
                                        "  Ажилтан: %s\n"
                                        "  Алдаа: %s\n"
                                        "  Томьёо: %s",
                                        ruled['code'], emp_name, e, ruled['python_code']
                                    )

                                # Алдаатай утгыг 0/False болгоно (бүх төрлийн алдааны хувьд адилхан)
                                try:
                                    with self.env.cr.savepoint():
                                        if ruled['rulefield_type'] == 'digit':
                                            if emp['is_edited'] == False:
                                                self.env.cr.execute(
                                                    'update llp_payroll_rule_value set value = %s where id = %s',
                                                    (0, emp['rule_value_id'])
                                                )
                                        elif ruled['rulefield_type'] == 'sign':
                                            if emp['is_edited'] == False:
                                                self.env.cr.execute(
                                                    "update llp_payroll_rule_value set char_value = %s where id = %s",
                                                    (False, emp['rule_value_id'])
                                                )
                                except Exception as e2:
                                    _logger.error(
                                        "Fallback update ч бас алдаа гаргалаа - rule: %s, employee: %s, error: %s",
                                        ruled['code'], emp['employee'], e2
                                    )
                        elif ruled['rule_type'] == 'regular':
                            if emp['is_edited'] == False:
                                try:
                                    with self.env.cr.savepoint():
                                        value = ruled['regular_number']
                                        if value is None:
                                            value = 0
                                        self.env.cr.execute(
                                            'update llp_payroll_rule_value set value = %s where id = %s',
                                            (value, emp['rule_value_id'])
                                        )
                                except Exception as e:
                                    if ruled['code'] not in errors_by_rule:
                                        errors_by_rule[ruled['code']] = {
                                            'error': str(e),
                                            'python_code': '',
                                            'name': ruled.get('name') or '',
                                        }
                                    _logger.error(
                                        "Payroll regular-rule update error - rule: %s, employee: %s, error: %s",
                                        ruled['code'], emp['employee'], e
                                    )
            self.env.cr.commit()
        # ★ Амжилттай тооцоологдсон утгуудыг ХАДГАЛСАН ХЭВЭЭР (commit хийгдсэн)
        #    үлдээгээд, дүрмийн алдаа болон ажилтны алдааг тусад нь харуулна.
        #    ZeroDivisionError аль алинд нь ороогүй — зөвхөн log-д бичигдэнэ.
        if errors_by_rule or employee_errors:
            # ★ Ижил дүрэм дээр олон ажилтанд яг адилхан алдааны текст давтагдвал,
            #    энэ нь ихэвчлэн тухайн ажилтны өгөгдлийн асуудал биш, харин
            #    дүрмийн python_code өөрөө буруу бичигдсэнээс болсон байдаг тул
            #    дүрмийн алдааны хэсэг рүү нэгтгэж шилжүүлнэ (олон давхардсан
            #    ажилтны мөр биш, 1 мөрөөр л харуулна).
            DUPLICATE_THRESHOLD = 3
            grouped = {}
            for item in employee_errors:
                key = item['rule']
                grouped.setdefault(key, []).append(item)
            remaining_employee_errors = []
            for rule_code, items in grouped.items():
                if len(items) >= DUPLICATE_THRESHOLD:
                    if rule_code not in errors_by_rule:
                        errors_by_rule[rule_code] = {
                            'error': items[0]['error'],
                            'python_code': items[0].get('python_code', ''),
                            'name': items[0].get('rule_name', ''),
                        }
                else:
                    remaining_employee_errors.extend(items)

            employee_errors = remaining_employee_errors
        if errors_by_rule or employee_errors:
            message_parts = []

            if errors_by_rule:
                max_show = 20
                rule_codes = list(errors_by_rule.keys())[:max_show]
                error_lines = []
                for code in rule_codes:
                    name = errors_by_rule[code].get('name') or ''
                    if name:
                        error_lines.append("Дүрэм: %s (%s)" % (code, name))
                    else:
                        error_lines.append("Дүрэм: %s" % code)
                extra = ''
                if len(errors_by_rule) > max_show:
                    extra = _("\n... болон бусад %s дүрэм дээр алдаа гарсан. Дэлгэрэнгүйг server log-оос харна уу.") % (
                        len(errors_by_rule) - max_show
                    )
                message_parts.append(
                    _("Доорх %(count)s дүрэм дээр алдаа гарсан тул тухайн утгыг 0 болгов:\n\n%(details)s%(extra)s") % {
                        'count': len(errors_by_rule),
                        'details': '\n'.join(error_lines),
                        'extra': extra,
                    }
                )
            if employee_errors:
                max_show_emp = 30
                emp_lines = []
                for item in employee_errors[:max_show_emp]:
                    rule_name = item.get('rule_name') or ''
                    rule_display = "%s (%s)" % (item['rule'], rule_name) if rule_name else item['rule']
                    emp_lines.append(
                        "Дүрэм: %s | Ажилтан: %s |" % (
                            rule_display, item['employee']
                        )
                    )
                    # ★ Энд дахин log хийхгүй — доор exception барих цэг дээр
                    #   (rule/employee/error) аль хэдийн бүрэн бичигдсэн байдаг.

                extra_emp = ''
                if len(employee_errors) > max_show_emp:
                    extra_emp = _("\n... болон бусад %s ажилтан дээр алдаа гарсан. Дэлгэрэнгүйг server log-оос харна уу.") % (
                        len(employee_errors) - max_show_emp
                    )

                message_parts.append(
                    _("Доорх ажилтнуудын өгөгдлөөс шалтгаалж утгыг 0 болгов:\n\n%(details)s%(extra)s") % {
                        'details': '\n'.join(emp_lines),
                        'extra': extra_emp,
                    }
                )

            raise UserError(_("Тооцоолол дуусав.\n\n") + '\n\n'.join(message_parts))
            # full_message = _("Тооцоолол дуусав.\n\n") + '\n\n'.join(message_parts)
            # return {
            #     'type': 'ir.actions.client',
            #     'tag': 'display_notification',
            #     'params': {
            #         'title': _('Анхаар'),
            #         'message': full_message,
            #         'type': 'warning',
            #         'sticky': True,  # гараар хаах хүртэл дэлгэц дээр үлдэнэ
            #         'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            #     }
            # }
    def get_from_previous_payroll(self,employee_id,code,start_date, end_date):
        value = 0.0

        query="select C.value as value \
        from llp_payroll A \
        left join llp_payroll_line B ON A.id=B.payroll_id \
        left join llp_payroll_rule_value C ON C.line_id = B.id \
        left join llp_payroll_rule D ON D.id = C.payroll_rule_id \
        left join llp_payroll_structure E ON E.id= A.struct_id \
        where A.state in ('confirmed') and E.struct_type ='salary_advance' and B.employee_id = %s and D.code ='%s' \
        and A.start_date between '%s' and '%s' and A.end_date between '%s' and '%s' "%(employee_id,code,start_date, end_date,start_date, end_date)

        self.env.cr.execute(query)
        fetch = self.env.cr.fetchone()
        if fetch:
            value = fetch[0]
        return value
    

    def create_history(self,state):
        history_obj = self.env['request.history']
        history_obj.create({'user_id':self._uid,
                                    'date':fields.Date.context_today(self),
                                    'type':state,
                                    'payroll_id':self.id
                                    })
    def action_open_edit_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payroll Import/Export',
            'res_model': 'llp.payroll.edit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payroll_id': self.id,
            }
        }

class LLPPayrollLine(models.Model):
    _name = 'llp.payroll.line'
    _description = "LLP payroll line"
    _order = "name asc"

    name = fields.Char(related="employee_id.name",string="Name", store=True, index=True)
    employee_id = fields.Many2one('hr.employee',string="HR Employee", store=True, index=True)
    payroll_id = fields.Many2one('llp.payroll',string="Payroll", ondelete='cascade', index=True)
    rule_value_ids = fields.One2many('llp.payroll.rule.value','line_id', string="Value")
    number = fields.Integer(string='№')
    payroll_state = fields.Selection(related='payroll_id.state', string="Payroll State", store=False)
    def action_computebyQUERY(self):
        return

    # Ажилтаны мөр дээрх утга буцаах
    @api.model
    def get_values(self,lines,fields):
        line_ids = []			
        line_ids = self.search([('id','in',lines)])
        line_obj = {}
        for line in line_ids:
            for field in fields:
                if field in line:	
                    if type(line[field]) is str or type(line[field]) is int or type(line[field]) is float:
                        line_obj[field]= line[field]
                    else:
                        line_obj[field]= line[field].id			
        return line_obj

    @api.model
    def get_line_values(self, payroll_id):
        payroll_id = self.env['llp.payroll'].search([('id','=',payroll_id)])
        lines = {}
        employees = []
        rules = [] 
        employee_values = {}
        employee_lines = {}
        is_edits = {}
        is_signs = {}
        decimals = {}
        sum_rules = {}
        
        struct_id = False

        for obj in payroll_id.line_ids:
            line = obj.sudo()
            struct_id = line.payroll_id.struct_id
            employees.append([line.employee_id.id,line.employee_id.name])
            if line.employee_id.id not in employee_values:
                employee_values.update({line.employee_id.id:{}})
                employee_lines.update({line.employee_id.id:{}})
                is_edits.update({line.employee_id.id:{}})
                is_signs.update({line.employee_id.id:{}})
            
            for rule in line.rule_value_ids:
                if [rule.payroll_rule_id.id,rule.payroll_rule_id.name] not in rules:
                    rules.append([
                        rule.payroll_rule_id.id, 
                        rule.payroll_rule_id.name, 
                        rule.payroll_rule_id.rulefield_type
                    ])
                    decimals.update({rule.payroll_rule_id.id: rule.payroll_rule_id.decimal_point})
                if rule.payroll_rule_id.id not in employee_values[line.employee_id.id]:
                    
                    is_edits[line.employee_id.id].update({rule.payroll_rule_id.id:rule.is_edit})
                    employee_lines[line.employee_id.id].update({rule.payroll_rule_id.id:rule.id})
                    if rule.payroll_rule_id.id not in sum_rules:
                        sum_rules.update({rule.payroll_rule_id.id:round(rule.value,2)})
                    else:
                        sum_rules[rule.payroll_rule_id.id] = sum_rules[rule.payroll_rule_id.id] + round(rule.value,2)
                    if rule.payroll_rule_id.rulefield_type in ['digit', 'from_previous_payroll']:
                        employee_values[line.employee_id.id].update({rule.payroll_rule_id.id:rule.value})
                        is_signs[line.employee_id.id].update({rule.payroll_rule_id.id:True})
                    else:
                        employee_values[line.employee_id.id].update({rule.payroll_rule_id.id:rule.char_value})
                        is_signs[line.employee_id.id].update({rule.payroll_rule_id.id:False})

        if struct_id:
            rules = []
            struct_line_ids = self.env['llp.payroll.structure.line'].search([('struct_id','=',struct_id.id)],order='sequence asc')
            for struct in struct_line_ids:
                if struct.rule_id.show_in_payroll:
                    if [struct.rule_id.id,struct.rule_id.name] not in rules:
                        rules.append([
                            struct.rule_id.id,
                            struct.rule_id.name+' '+struct.rule_id.code, 
                            bool(struct.rule_id.is_show_sum), 
                            struct.rule_id.rulefield_type, 
                            struct.rule_id.ruleview_type
                        ])

        lines.update({
            'employees':employees,
            'rules':rules,
            'employee_values':employee_values,
            'employee_lines':employee_lines,
            'decimals':decimals,
            'is_signs':is_signs,
            'sum_rules':sum_rules,
            'is_edits':is_edits
            })
        return lines
    
    # @api.model
    # def update_value(self, rule_value_id, value):
    #     rule_value = self.env['llp.payroll.rule.value'].browse(rule_value_id)
    #     # digit / from_previous_payroll -> тоон 'value' талбарт,
    #     # бусад (жишээ нь 'sign') -> текст 'char_value' талбарт хадгална
    #     if rule_value.rulefield_type in ('digit', 'from_previous_payroll'):
    #         rule_value.write({'value': value, 'is_edited': True})
    #     else:
    #         rule_value.write({'char_value': value, 'is_edited': True})
    #     return True
    @api.model
    def update_value(self, rule_value_id, value):
        rule_value = self.env['llp.payroll.rule.value'].browse(rule_value_id)
        current_type = rule_value.payroll_rule_id.rulefield_type  # дүрмийн одоогийн бодит төрөл

        vals = {'is_edited': True}

        if current_type in ('digit', 'from_previous_payroll'):
            try:
                vals['value'] = float(value or 0.0)
            except (TypeError, ValueError):
                raise UserError(_(
                    "'%s' гэсэн утга буруу байна. '%s' дүрэм зөвхөн тоон утга авдаг."
                ) % (value, rule_value.payroll_rule_id.name))
        else:
            vals['char_value'] = str(value) if value else ''

        # rule_value дээрх хуучирсан snapshot-ыг мөн шинэчилж, дараагийн удаа
        # ижил алдаа гарахаас сэргийлнэ
        if rule_value.rulefield_type != current_type:
            vals['rulefield_type'] = current_type

        rule_value.write(vals)
        return True

class LLPPayrollRuleValue(models.Model):
    _name = 'llp.payroll.rule.value'
    _description = "LLP payroll"
    _order = "create_date desc"

    line_id = fields.Many2one('llp.payroll.line', string="Lines",ondelete='cascade',index=True)
    payroll_rule_id = fields.Many2one('llp.payroll.rule', string="Rule", ondelete='restrict',index=True)
    rulefield_type = fields.Selection([
        ('digit','Digit'),
        ('sign','Sign'),
        ('from_previous_payroll','Get from previous payroll')
        ], string="Rule field type", default="digit")
    currency_id = fields.Many2one('res.currency', string="Currency")
    value = fields.Monetary(string="Value", currency_field='currency_id', digits=(16, 2))
    char_value = fields.Char(string="Value")
    sequence = fields.Integer(string="Value")
    is_edit = fields.Boolean(string="is_edit")
    is_edited = fields.Boolean(string="Is edited",default=False,index=True)
    attend = fields.Text(string="Formula",index=True)
    decimal_point = fields.Integer(string='Decimal point',index=True)
    show_in_payroll = fields.Boolean(string="Show in payroll Active",default=True,index=True)
    is_show = fields.Boolean(string="Is show" ,default=True,index=True)
    is_sum_view = fields.Boolean(string="Is sum view" ,default=False,index=True)

    is_debt_rule = fields.Boolean(
        string='Is Debt Rule',
        default=False,
        index=True,
    )

    is_vacation_rule = fields.Boolean(
        string='Is Vacation Rule',
        default=False,
        index=True,
    )
	

class RequestHistory(models.Model):
    """ Ажлын урсгалын түүх """
    
    _name = 'request.history'
    _description = 'Request History'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    STATE_SELECTION = [('draft','Draft'),
                       ('sent','Sent'),#Илгээгдсэн
                       ('approved',u'Зөвшөөрсөн'),#Зөвшөөрсөн
                       ('verified',u'Хянасан'),#Хянасан
                       ('next_confirm_user',u'Зөвшөөрсөн'),#Дараагийн батлах хэрэглэгчид илгээгдсэн
                       ('confirmed',u'Баталсан'),#Батласан
                       ('tender_created',u'Тендер үүссэн'),#Тендер үүссэн
                       ('sent_to_supply',u'Хангамжид илгээгдсэн'),#Хангамжаарх худалдан авалт
                       ('fulfil_request',u'Биелүүлэх хүсэлт'),# Биелүүлэх хүсэлт
                       ('fulfill',u'Биелүүлэх'),# Биелүүлэх
                       ('retrived',u'Буцаагдсан'),# Буцаагдсан
                       ('retrive_request',u'Буцаагдах хүсэлт'),# Буцаагдах хүсэлт
                       ('rejected',u'Rejected'),
                       ('assigned',u'Хувиарласан'),
                       ('canceled',u'Цуцлагдсан'),#Цуцлагдсан
                       ('purchased',u'Худалдан авалт үүссэн'),#Худалдан авалт үүссэн
                       ('purchase',U'Худалдан авах захиалга'),#Худалдан авалт үүссэн
                       ('sent_to_supply_manager',u'Бараа тодорхойлох'),#Хангамж импортын менежер
                       ('closed',u'Хаагдсан'),
                       ('done',u'Дууссан'),
                       ('anket', 'Анкет'),
                        ('exam', 'Шалгалт'),
                        ('interview', 'Ярилцлага'),
                        ('professional', 'Мэргэжлийн шалгалт'),	
                        ('interview2', 'Ярилцлага2'),	
                        ('task', 'Даалгавар'),	
                        ('interview3', 'Ярилцлага3'),	
                       ('receive',u'Хүлээн авах'),
                       ('completed','Completed'),
                       ('pending',u'Хүлээгдэж буй'),
                       ('verify',u'Хянах'),
                                   ]
    user_id = fields.Many2one('res.users', string='User', required=True)
    date = fields.Datetime(string='Action Date', required=True)
    type = fields.Selection(STATE_SELECTION, string='Type', required=True, default='draft')
    comment = fields.Text(string='Comment')
    sequence = fields.Integer(string='Sequence', default=1)

class LLPPayrollHistory(models.Model):
	_inherit = 'request.history'

	payroll_id = fields.Many2one('llp.payroll', string='Payroll', ondelete="cascade")

class PayrollPaymentHistory(models.Model):
    _name = 'payroll.payment.history'
    _order = 'create_date desc'

    move_id = fields.Many2one('account.move', string="Move")
    state = fields.Selection(
        related="move_id.state",
        string="State",
        store=True,
        index=True,
        readonly=True
    )
    payroll_id = fields.Many2one('llp.payroll', string="Payroll")