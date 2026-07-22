import time 
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round as round
from odoo.exceptions import UserError
from odoo import api, fields, models, _
from datetime import date, datetime, timedelta
from dateutil import relativedelta
from datetime import date
from odoo.exceptions import ValidationError
from markupsafe import Markup
from dateutil.relativedelta import relativedelta

class LLPPayroll(models.Model):
    _inherit = 'llp.payroll'




    workflow_active_line_ids = fields.Many2many(related='dynamic_workflow_id.active_line_ids')
    line_state = fields.Many2one('dynamic.workflow.line',domain="[('id', 'in', workflow_active_line_ids)]", copy=False)
    is_super = fields.Boolean(related='line_state.is_super')
    state_id = fields.Many2one(related='line_state.state_id', string='State Line', store=True)
    waiting_user_ids = fields.Many2many('res.users', 'llp_payroll_waiting_user_rel', 'llp_payroll_id', 'user_id', string='Waiting Users', compute='_compute_waiting_user_ids', store=False)

    approve_ids = fields.Many2many('res.users', 'approve_user_llp_payroll_rel', 'llp_payroll_id', 'res_users_id', string='Approve Users')
    confirmed_date = fields.Date('')
    log_action_text = fields.Char('Action')
    log_comment = fields.Char('Comment')
    state_log_ids = fields.One2many("state.log", "llp_payroll_id", copy=False)
    # workflow_id = fields.Many2one('dynamic.workflow', string='Work flow' , tracking=True, domain="[('model_id.model', '=', 'llp.payroll')]",required='true')

    allowed_workflow_ids = fields.Many2many(
            'dynamic.workflow',
            compute='_compute_allowed_workflow_ids',
        )

    dynamic_workflow_id = fields.Many2one(
            'dynamic.workflow', 
            string='Workflow', 
            domain="[('id', 'in', allowed_workflow_ids)]"
        )

    @api.depends('company_id')
    def _compute_allowed_workflow_ids(self):
        # employee = self.env.user.employee_id
        # dept = employee.department_id
        company = self.company_id
        for rec in self:
            rec.allowed_workflow_ids = self.env['dynamic.workflow'].search([
                '|',
                    ('company_id', '=', False),
                    ('company_id', '=', company.id),
                ('model_id.model', '=', 'llp.payroll'),
                # Хэрэв ирээдүйд department-аар шүүх шаардлагатай бол:
                # '|',
                #     ('department_ids', '=', False),
                #     ('department_ids', 'in', dept.ids),
            ])
 


    def button_action_cancel(self):
        ctx = (self.env.context).copy()
        ctx['default_llp_payroll_id'] = self.id
        ctx['default_approve_code'] = 11
        ctx['default_comment_required'] = True
        return {
            'name': _('Cancelled_from_Confirmed'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'dynamic.workflow.confirm.wizard',
            'view_id': self.env.ref('llp_dynamic_workflow_base.view_dynamic_workflow_confirm_form_wizard').id,
            'target': 'new',
            'context': ctx,
            }
    def button_cancel(self):
        if self.dynamic_workflow_id:
            self.write({'line_state': False})
        self.state='cancel'

        
    def button_send_draft(self):
        self.state = 'draft'


    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end:
                if record.date_end < record.date_start:
                    raise ValidationError(_('Сунгах өдөр нь ирэх өдөрөөс өмнө байж болохгүй!'))


    
    # def set_number(self):
    #     for rec in self:
    #         if not rec.name:
    #             # sequence = self.env['ir.sequence'].next_by_code('time.planing')

    #             date_from = fields.Date.to_date(rec.date_from)

    #             type_label = dict(
    #                 rec._fields['type'].selection
    #             ).get(rec.type)
    #             # Example: 202606-202607
    #             month_range = ''
    #             if date_from:
    #                 month_range = f'{date_from:%Y}-{date_from:%m}-{type_label}'

    #             department_code = rec.department_id.name or 'DEP'

    #             rec.name = f'{month_range}-{department_code}'


    @api.depends('line_state', 'state')
    def _compute_waiting_user_ids(self):
        for rec in self:
            if rec.line_state.is_external:
                rec.waiting_user_ids = False
            else:
                rec.waiting_user_ids = rec.line_state._get_users_waiting(rec.create_uid) if rec.line_state else False

        
                
    def action_sent(self):
        if self.dynamic_workflow_id:
            self.line_state = self.dynamic_workflow_id._get_first_flow(self.id, self.name, self._name, 'Орон тоо')
            if not self.line_state:
                self.action_confirmed()
            else:
                approve_user_ids = []
                for line in self.workflow_active_line_ids:
                    approve_user_ids += line._get_users_waiting(self.create_uid)
                self.approve_ids = list(set(approve_user_ids)) if approve_user_ids else []

        # if not self.name:
        #     self.set_number()
        self.state='sent'
        if line.state:
            self.confirmed_notification()

    
    def confirm_state(self):
        self.log_action_text = 'Батлав'
        self._confirm_state()
        
    def return_state(self):
        ctx = self.env.context.copy()
        ctx.update({
            'default_llp_payroll_id': self.id,
            'default_approve_code': 2,
            'default_comment_required': True
        })
        if self.line_state._check_user_access(self.create_uid):
            return {
                'name': _('Return'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'dynamic.workflow.confirm.wizard',
                'view_id': self.env.ref('llp_dynamic_workflow_base.view_dynamic_workflow_confirm_form_wizard').id,
                'target': 'new',
                'context': ctx,
            }
        else:
            raise UserError(_('You do not have permission to perform this action.'))
        
    def cancel_state(self):
        ctx = (self.env.context).copy()
        ctx['default_llp_payroll_id'] = self.id
        ctx['default_approve_code'] = 3
        ctx['default_comment_required'] = True
        if self.line_state._check_user_access(self.create_uid):
            return {
                'name': _('Cancel'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'dynamic.workflow.confirm.wizard',
                'view_id': self.env.ref('llp_dynamic_workflow_base.view_dynamic_workflow_confirm_form_wizard').id,
                'target': 'new',
                'context': ctx,
              }
        else:
                raise UserError('Танд энэ үйлдлийг хийх эрх байхгүй байна.')
        
    def _confirm_state(self, no_access = False):
        self.line_state = self.line_state._approve(self.create_uid,self.id, self.name, self._name, 'Орон тоо', no_access=no_access)
        if self.line_state:
            self.confirmed_notification()
        # Цаашаа батлах урсгал байхгүй бол
        if not self.line_state:
            self.action_confirmed()
            
    def _return_state(self):
        self.line_state = self.line_state._return(self.create_uid,self.id, self.name, self._name, 'Орон тоо')
        #Буцаах батлах урсгал байхгүй бол
        if not self.line_state:
            self.action_draft()

    # #cancel хийдэг функцийг өргөжүүлэх
    def action_confirmed(self):
        self.state='confirmed'
        self.action_notify_followers()
        self.confirmed_date = fields.Date.today()
        
    def action_send_to_draft_from_nybo(self):
        self.state='draft'
    
    def action_receive_nybo(self):
        self.state='accountant'
        self.action_notify_accountant()
        # self.lock_timeplan()

    def action_draft(self):
        if self.dynamic_workflow_id:
            self.write({'line_state': False})
        self.state='draft'



    def _cancel_state(self, no_access = False):
        if no_access:
            return self.button_cancel()
        if self.line_state._check_user_access(self.create_uid):
            return self.button_cancel()
        

    # def cancel_from_accountant(self):
    #     self.state = 'cancel'
    #     self.cancel_timeplan()

    def write(self, vals):
        #state log
        # not dynamic state log
        if "state" in vals:
            log_content = self.env.context.get('log_content') or ''
            for rec in self:
                last_date = self.env['state.log'].search([('llp_payroll_id', '=', rec.id)], order="create_date desc", limit=1)
                state_str = dict(self._fields['state']._description_selection(self.env)).get(rec.state)    # Орчуулагдсан төлөв
                values = {
                    'llp_payroll_id': rec.id,
                    'created_user_id': self.env.user.id,
                    'state_str': state_str,
                    'content': log_content,
                    'action_text': rec.log_action_text,
                    'modified_date': fields.datetime.now(),
                    "elapsed_time": (fields.datetime.now() - last_date[0]["create_date"]).total_seconds() / 3600 if last_date else 0
                }
                self.env['state.log'].create(values)
                rec.log_action_text = False


        # dynamic workflow change
        if "line_state" in vals:
            log_content = self.env.context.get('log_content') or ''
            for rec in self:
                waiting_user_ids = []
                line_state_id = self.env['dynamic.workflow.line'].browse(vals["line_state"])
                # delete huleegdej bui
                rec.mapped('state_log_ids').filtered(lambda line: line.content == 'Хүлээгдэж буй').unlink()
                rec.waiting_user_ids = False
                if vals["line_state"] != False:
                    # tus tuluw deer batlah humuus deer huleegdej bui tuluw nemeh
                    for id in line_state_id._get_users_waiting(rec.create_uid):
                        values = {
                            'llp_payroll_id': rec.id,
                            'created_user_id': id,
                            'state_str': line_state_id.state_id.name,
                            'content': log_content,
                            'modified_date': fields.datetime.now(),
                            "elapsed_time": 0,
                            "approved": 0
                        }
                        self.env['state.log'].create(values)
                        waiting_user_ids.append(id)
                rec.waiting_user_ids = waiting_user_ids
                #Add state log
                if rec.line_state.state_id.name:
                    log_content = self.env.context.get('log_content') or ''
                    last_date = self.env['state.log'].search([('llp_payroll_id', '=', rec.id)], order="create_date desc", limit=1)
                    values = {
                        'llp_payroll_id': rec.id,
                        'created_user_id': self.env.user.id,
                        'state_str': rec.line_state.state_id.name,
                        'content': log_content,
                        'action_text': rec.log_action_text,
                        'modified_date': fields.datetime.now(),
                        "elapsed_time": (fields.datetime.now() - last_date[0]["create_date"]).total_seconds() / 3600 if last_date else 0,
                        "approved": 0
                    }
                    self.env['state.log'].create(values)
                    rec.log_action_text = False

        return super(LLPPayroll, self).write(vals)
    


    
    
    def get_request_user_signature(self,ids):
        report_id = self.browse(ids)
        html = '<table>'
        image_str = '_____________________'
        if report_id.create_uid.digital_signature_from_file:
            image_buf = (report_id.create_uid.digital_signature_from_file).decode('utf-8')
            image_str = '<img alt="Embedded Image" width="80" src="data:image/png;base64,%s" />'%(image_buf)
        html += u'%s'%(image_str)
        html += '</table>'
        return html


    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = False
        default['state'] = 'draft'
        return super().copy(default)
    

        
    def confirmed_notification(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')            
        base_url = (base_url or '').rstrip('/')
        action = self.env["ir.actions.actions"]._for_xml_id("llp_payroll.action_llp_payroll")

        for rec in self:
            users = rec.waiting_user_ids.filtered(lambda u: u.active and u.partner_id)

            if not users:
                continue

            payroll_url = (
                f"{base_url}/web"
                f"#id={rec.id}"
                f"&model={rec._name}"
                f"&view_type=form"
                # f"&action={action.id if action else ''}"
                f"&action={action['id']}")
            
            type_name = dict(rec.struct_id._fields['struct_type'].selection).get(rec.struct_id.struct_type, '')

            for user in users:

                body = Markup(f"""
                    <p style="font-family:Arial;font-size:10pt;">
                        Танд "{rec.line_state.name or ''}" төлөвтэй Цалин бодолт хянагдахаар ирлээ
                    </p>

                    <p style="font-family:Arial;font-size:10pt;"> * Цалин бодолт дугаар: {rec.name or ''}</p>
                    <p style="font-family:Arial;font-size:10pt;"> * Цалин бодолт төрөл: {type_name or ''}</p>

                    <br/>
                    <a href="{payroll_url}" target="_blank"
                    style="background-color:#976686;padding:8px 16px;text-decoration:none;color:#fff;border-radius:5px;font-family:Arial;font-size:10pt;">
                        Цалин бодолтын холбоос
                    </a>

                    <br/><br/>

                """)

                channel_info = self.env['discuss.channel'].channel_get([
                    user.partner_id.id
                ])
                channel = self.env['discuss.channel'].browse(channel_info['id'])

                channel.message_post(
                    body=body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )


    def action_notify_followers(self):
        Channel = self.env['discuss.channel'].sudo()

        for rec in self:
            partners = rec.message_follower_ids.mapped('partner_id').filtered(lambda p: p.user_ids)

            if not partners:
                raise UserError("Followers алга байна.")
            type_name = dict(rec.struct_id._fields['struct_type'].selection).get(rec.struct_id.struct_type, '')

            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')     
            base_url = (base_url or '').rstrip('/')
            action = self.env["ir.actions.actions"]._for_xml_id("llp_payroll.action_llp_payroll")

            payroll_url = (
                f"{base_url}/web"
                f"#id={rec.id}"
                f"&model={rec._name}"
                f"&view_type=form"
                f"&action={action['id']}")

            body = Markup(f"""
                <p>
                    {rec.name or ''} нэртэй 
                    {type_name or ''} ангилалын Цалин бодолт батлагдаж,
                    батлагдсан төлөвт орлоо.
                </p>
                <a href="{payroll_url}" target="_blank"
                style="background-color:#976686;padding:8px 16px;text-decoration:none;color:#fff;border-radius:5px;font-family:Arial;font-size:10pt;">
                    Цалин бодолтын холбоос
                </a>

            """)

            for partner in partners:
                channel = Channel.channel_get([partner.id])

                channel.message_post(
                    body=body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )



class StateLog(models.Model):
    _inherit = 'state.log'

    llp_payroll_id = fields.Many2one('llp.payroll' , string='LLP Payroll')

class DynamicWorkflowConfirmWizardInherit(models.TransientModel):
    _inherit = 'dynamic.workflow.confirm.wizard'

    llp_payroll_id = fields.Many2one('llp.payroll')

    def _confirm(self):
        self.ensure_one()

        if self.llp_payroll_id:
            park_req = self.llp_payroll_id.with_context(log_content=self.comment or '')
            if self.approve_code == 2:
                park_req.log_action_text = 'Буцаав'
                park_req._return_state()
            elif self.approve_code == 3:
                park_req.log_action_text = 'Буцаав'
                park_req._cancel_state()
            elif self.approve_code == 11:
                park_req.log_action_text = 'Буцаав'
            
            return {'type': 'ir.actions.act_window_close'}
        return super()._confirm()
    

