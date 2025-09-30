from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EstateBuildingUnit(models.Model):
    _name = 'estate.building.unit'
    _description = 'Building Unit (Apartment)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='اسم الشقة/الوحدة', required=True, tracking=True)
    building_id = fields.Many2one('estate.building', string='البناية', required=True, ondelete='cascade', tracking=True)
    floor = fields.Integer(string='رقم الطابق', tracking=True)
    unit_number = fields.Char(string='رقم الشقة', tracking=True)

    department_id = fields.Many2one('hr.department', string='القسم (اختياري)')

    tenant_id = fields.Many2one('res.partner', string='المستأجر الحالي')
    contract_ids = fields.One2many('rent.contract', 'unit_id', string='عقود الإيجار')

    active_contract_id = fields.Many2one('rent.contract', string='العقد الفعّال', compute='_compute_active_contract', store=False)
    occupied = fields.Boolean(string='مشغولة؟', compute='_compute_active_contract', store=False)

    @api.depends('contract_ids.state', 'contract_ids.start_date', 'contract_ids.end_date')
    def _compute_active_contract(self):
        today = fields.Date.context_today(self)
        for u in self:
            active = u.contract_ids.filtered(lambda c: c.state == 'active' and (not c.end_date or c.end_date >= today) and (not c.start_date or c.start_date <= today))
            u.active_contract_id = active[:1].id if active else False
            u.occupied = bool(active)