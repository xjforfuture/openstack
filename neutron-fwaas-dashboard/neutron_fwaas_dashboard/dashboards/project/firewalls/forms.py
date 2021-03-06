# Copyright 2013, Big Switch Networks, Inc
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon.utils import validators

from openstack_dashboard import api
from openstack_dashboard import policy

from neutron_fwaas_dashboard.api import fwaas as api_fwaas

port_validator = validators.validate_port_or_colon_separated_port_range

LOG = logging.getLogger(__name__)


class UpdateRule(forms.SelfHandlingForm):
    name = forms.CharField(max_length=80, label=_("Name"), required=False)
    description = forms.CharField(
        required=False,
        max_length=80, label=_("Description"))
    protocol = forms.ThemableChoiceField(
        label=_("Protocol"), required=False,
        choices=[('tcp', _('TCP')), ('udp', _('UDP')), ('icmp', _('ICMP')),
                 ('any', _('ANY'))],
        help_text=_('Protocol for the firewall rule'))
    action = forms.ThemableChoiceField(
        label=_("Action"), required=False,
        choices=[('allow', _('ALLOW')), ('deny', _('DENY')),
                 ('reject', _('REJECT'))],
        help_text=_('Action for the firewall rule'))
    source_ip_address = forms.IPField(
        label=_("Source IP Address/Subnet"),
        version=forms.IPv4 | forms.IPv6,
        required=False, mask=True,
        help_text=_('Source IP address or subnet'))
    destination_ip_address = forms.IPField(
        label=_('Destination IP Address/Subnet'),
        version=forms.IPv4 | forms.IPv6,
        required=False, mask=True,
        help_text=_('Destination IP address or subnet'))
    source_port = forms.CharField(
        max_length=80,
        label=_("Source Port/Port Range"),
        required=False,
        validators=[port_validator],
        help_text=_('Source port (integer in [1, 65535] or range in a:b)'))
    destination_port = forms.CharField(
        max_length=80,
        label=_("Destination Port/Port Range"),
        required=False,
        validators=[port_validator],
        help_text=_('Destination port (integer in [1, 65535] or range'
                    ' in a:b)'))
    ip_version = forms.ThemableChoiceField(
        label=_("IP Version"), required=False,
        choices=[('4', '4'), ('6', '6')],
        help_text=_('IP Version for Firewall Rule'))
    shared = forms.BooleanField(label=_("Shared"), required=False)
    enabled = forms.BooleanField(label=_("Enabled"), required=False)

    failure_url = 'horizon:project:firewalls:index'

    def __init__(self, request, *args, **kwargs):
        super(UpdateRule, self).__init__(request, *args, **kwargs)
        # Only admin user can update the 'shared' attribute
        self.ignore_shared = False
        if not policy.check((("neutron-fwaas",
                              "update_firewall_rule:shared"),),
                            request):
            self.fields['shared'].widget = forms.CheckboxInput(
                attrs={'readonly': 'readonly', 'disabled': 'disabled'})
            self.fields['shared'].help_text = _(
                'Non admin users are not allowed to set the shared property '
                'of the rule.')
            self.ignore_shared = True

    def handle(self, request, context):
        rule_id = self.initial['id']
        name_or_id = context.get('name') or rule_id
        if context['protocol'] == 'any':
            context['protocol'] = None
        for f in ['source_ip_address', 'destination_ip_address',
                  'source_port', 'destination_port']:
            if not context[f]:
                context[f] = None

        # Remove 'shared' from the context if the user is not allowed to
        # change this field
        if self.ignore_shared and 'shared' in context:
            del context['shared']

        try:
            rule = api_fwaas.rule_update(request, rule_id, **context)
            msg = _('Rule %s was successfully updated.') % name_or_id
            messages.success(request, msg)
            return rule
        except Exception as e:
            LOG.error('Failed to update rule %(id)s: %(reason)s',
                      {'id': rule_id, 'reason': e})
            msg = (_('Failed to update rule %(name)s: %(reason)s') %
                   {'name': name_or_id, 'reason': e})
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)


class UpdatePolicy(forms.SelfHandlingForm):
    name = forms.CharField(max_length=80, label=_("Name"), required=False)
    description = forms.CharField(required=False,
                                  max_length=80, label=_("Description"))
    shared = forms.BooleanField(label=_("Shared"), required=False)
    audited = forms.BooleanField(label=_("Audited"), required=False)

    failure_url = 'horizon:project:firewalls:index'

    def __init__(self, request, *args, **kwargs):
        super(UpdatePolicy, self).__init__(request, *args, **kwargs)
        # Only admin user can update the 'shared' attribute
        self.ignore_shared = False
        if not policy.check((("neutron-fwaas",
                              "update_firewall_policy:shared"),),
                            request):
            self.fields['shared'].widget = forms.CheckboxInput(
                attrs={'readonly': 'readonly', 'disabled': 'disabled'})
            self.fields['shared'].help_text = _(
                'Non admin users are not allowed to set the shared property '
                'of the policy.')
            self.ignore_shared = True

    def handle(self, request, context):
        policy_id = self.initial['id']
        name_or_id = context.get('name') or policy_id

        # Remove 'shared' from the context if the user is not allowed to
        # change this field
        if self.ignore_shared and 'shared' in context:
            del context['shared']

        try:
            policy = api_fwaas.policy_update(request, policy_id, **context)
            msg = _('Policy %s was successfully updated.') % name_or_id
            messages.success(request, msg)
            return policy
        except Exception as e:
            LOG.error('Failed to update policy %(id)s: %(reason)s',
                      {'id': policy_id, 'reason': e})
            msg = (_('Failed to update policy %(name)s: %(reason)s') %
                   {'name': name_or_id, 'reason': e})
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)


class UpdateFirewall(forms.SelfHandlingForm):
    name = forms.CharField(max_length=80,
                           label=_("Name"),
                           required=False)
    description = forms.CharField(max_length=80,
                                  label=_("Description"),
                                  required=False)
    firewall_policy_id = forms.ThemableChoiceField(label=_("Policy"))
    admin_state_up = forms.BooleanField(label=_("Enable Admin State"),
                                        required=False)
    failure_url = 'horizon:project:firewalls:index'

    def __init__(self, request, *args, **kwargs):
        super(UpdateFirewall, self).__init__(request, *args, **kwargs)

        try:
            tenant_id = self.request.user.tenant_id
            policies = api_fwaas.policy_list_for_tenant(request, tenant_id)
            policies = sorted(policies, key=lambda policy: policy.name)
        except Exception:
            exceptions.handle(request,
                              _('Unable to retrieve policy list.'))
            policies = []

        policy_id = kwargs['initial']['firewall_policy_id']
        policy_name = [p.name for p in policies if p.id == policy_id][0]

        firewall_policy_id_choices = [(policy_id, policy_name)]
        for p in policies:
            if p.id != policy_id:
                firewall_policy_id_choices.append((p.id, p.name_or_id))

        self.fields['firewall_policy_id'].choices = firewall_policy_id_choices

    def handle(self, request, context):
        firewall_id = self.initial['id']
        name_or_id = context.get('name') or firewall_id
        try:
            firewall = api_fwaas.firewall_update(request, firewall_id,
                                                 **context)
            msg = _('Firewall %s was successfully updated.') % name_or_id
            messages.success(request, msg)
            return firewall
        except Exception as e:
            LOG.error('Failed to update firewall %(id)s: %(reason)s',
                      {'id': firewall_id, 'reason': e})
            msg = (_('Failed to update firewall %(name)s: %(reason)s') %
                   {'name': name_or_id, 'reason': e})
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)


class InsertRuleToPolicy(forms.SelfHandlingForm):
    firewall_rule_id = forms.ThemableChoiceField(label=_("Insert Rule"))
    insert_before = forms.ThemableChoiceField(label=_("Before"),
                                              required=False)
    insert_after = forms.ThemableChoiceField(label=_("After"),
                                             required=False)

    failure_url = 'horizon:project:firewalls:index'

    def __init__(self, request, *args, **kwargs):
        super(InsertRuleToPolicy, self).__init__(request, *args, **kwargs)

        try:
            tenant_id = self.request.user.tenant_id
            all_rules = api_fwaas.rule_list_for_tenant(request, tenant_id)
            all_rules = sorted(all_rules, key=lambda rule: rule.name_or_id)

            available_rules = [r for r in all_rules
                               if not r.firewall_policy_id]

            current_rules = []
            for r in kwargs['initial']['firewall_rules']:
                r_obj = [rule for rule in all_rules if r == rule.id][0]
                current_rules.append(r_obj)

            available_choices = [(r.id, r.name_or_id) for r in available_rules]
            current_choices = [(r.id, r.name_or_id) for r in current_rules]

        except Exception as e:
            LOG.error('Failed to retrieve available rules: %s', e)
            msg = _('Failed to retrieve available rules: %s') % e
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)

        self.fields['firewall_rule_id'].choices = available_choices
        self.fields['insert_before'].choices = [('', '')] + current_choices
        self.fields['insert_after'].choices = [('', '')] + current_choices

    def handle(self, request, context):
        policy_id = self.initial['id']
        policy_name_or_id = self.initial['name'] or policy_id
        try:
            insert_rule_id = context['firewall_rule_id']
            insert_rule = api_fwaas.rule_get(request, insert_rule_id)
            body = {'firewall_rule_id': insert_rule_id,
                    'insert_before': context['insert_before'],
                    'insert_after': context['insert_after']}
            policy = api_fwaas.policy_insert_rule(request, policy_id, **body)
            msg = _('Rule %(rule)s was successfully inserted to policy '
                    '%(policy)s.') % {
                        'rule': insert_rule.name or insert_rule.id,
                        'policy': policy_name_or_id}
            messages.success(request, msg)
            return policy
        except Exception as e:
            LOG.error('Failed to insert rule to policy %(id)s: %(reason)s',
                      {'id': policy_id, 'reason': e})
            msg = (_('Failed to insert rule to policy %(name)s: %(reason)s') %
                   {'name': policy_id, 'reason': e})
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)


class RemoveRuleFromPolicy(forms.SelfHandlingForm):
    firewall_rule_id = forms.ThemableChoiceField(label=_("Remove Rule"))

    failure_url = 'horizon:project:firewalls:index'

    def __init__(self, request, *args, **kwargs):
        super(RemoveRuleFromPolicy, self).__init__(request, *args, **kwargs)

        try:
            tenant_id = request.user.tenant_id
            all_rules = api_fwaas.rule_list_for_tenant(request, tenant_id)

            current_rules = []
            for r in kwargs['initial']['firewall_rules']:
                r_obj = [rule for rule in all_rules if r == rule.id][0]
                current_rules.append(r_obj)

            current_choices = [(r.id, r.name_or_id) for r in current_rules]
        except Exception as e:
            LOG.error('Failed to retrieve current rules in policy %(id)s: '
                      '%(reason)s',
                      {'id': self.initial['policy_id'], 'reason': e})
            msg = (_('Failed to retrieve current rules in policy %(name)s: '
                     '%(reason)s') %
                   {'name': self.initial['name'], 'reason': e})
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)

        self.fields['firewall_rule_id'].choices = current_choices

    def handle(self, request, context):
        policy_id = self.initial['id']
        policy_name_or_id = self.initial['name'] or policy_id
        try:
            remove_rule_id = context['firewall_rule_id']
            remove_rule = api_fwaas.rule_get(request, remove_rule_id)
            body = {'firewall_rule_id': remove_rule_id}
            policy = api_fwaas.policy_remove_rule(request, policy_id, **body)
            msg = _('Rule %(rule)s was successfully removed from policy '
                    '%(policy)s.') % {
                        'rule': remove_rule.name or remove_rule.id,
                        'policy': policy_name_or_id}
            messages.success(request, msg)
            return policy
        except Exception as e:
            LOG.error('Failed to remove rule from policy %(id)s: %(reason)s',
                      {'id': policy_id, 'reason': e})
            msg = (_('Failed to remove rule from policy %(name)s: %(reason)s')
                   % {'name': self.initial['name'], 'reason': e})
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)


class AddRouterToFirewall(forms.SelfHandlingForm):
    router_ids = forms.MultipleChoiceField(
        label=_("Add Routers"),
        required=False,
        widget=forms.ThemableCheckboxSelectMultiple(),
        help_text=_("Add selected router(s) to the firewall."))

    failure_url = 'horizon:project:firewalls:index'

    def __init__(self, request, *args, **kwargs):
        super(AddRouterToFirewall, self).__init__(request, *args, **kwargs)
        try:
            router_choices = self.get_router_choices(request, kwargs)
            self.fields['router_ids'].choices = router_choices
        except Exception as e:
            LOG.error('Failed to retrieve available routers: %s', e)
            msg = _('Failed to retrieve available routers: %s') % e
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)

    def get_router_choices(self, request, kwargs):
        tenant_id = self.request.user.tenant_id
        routers_list = api_fwaas.firewall_unassociated_routers_list(
            request, tenant_id)
        return [(r.id, r.name_or_id) for r in routers_list]

    def get_new_router_ids(self, context):
        existing_router_ids = self.initial['router_ids']
        add_router_ids = context['router_ids']
        return add_router_ids + existing_router_ids

    def handle(self, request, context):
        firewall_id = self.initial['id']
        firewall_name_or_id = self.initial['name'] or firewall_id
        try:
            body = {'router_ids': self.get_new_router_ids(context)}
            firewall = api_fwaas.firewall_update(request, firewall_id, **body)
            msg = (_('Router(s) was/were successfully added to firewall '
                     '%(firewall)s.') %
                   {'firewall': firewall_name_or_id})
            messages.success(request, msg)
            return firewall
        except Exception as e:
            LOG.error('Failed to add router(s) to firewall %(id)s: %(reason)s',
                      {'id': firewall_id, 'reason': e})
            msg = (_('Failed to add router(s) to firewall %(name)s: '
                     '%(reason)s') %
                   {'name': firewall_name_or_id, 'reason': e})
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)


class RemoveRouterFromFirewall(forms.SelfHandlingForm):
    router_ids = forms.MultipleChoiceField(
        label=_("Associated Routers"),
        required=False,
        widget=forms.ThemableCheckboxSelectMultiple(),
        help_text=_("Unselect the router(s) to be removed from firewall."))

    failure_url = 'horizon:project:firewalls:index'

    def __init__(self, request, *args, **kwargs):
        super(RemoveRouterFromFirewall, self).__init__(request,
                                                       *args, **kwargs)
        try:
            router_choices = self.get_router_choices(request, kwargs)
            self.fields['router_ids'].choices = router_choices
        except Exception as e:
            LOG.error('Failed to retrieve current routers in firewall %(id)s: '
                      '%(reason)s',
                      {'id': self.initial['firewall_id'], 'reason': e})
            msg = (_('Failed to retrieve current routers in firewall '
                     '%(name)s: %(reason)s') %
                   {'name': self.initial['name'], 'reason': e})
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)

    def get_router_choices(self, request, kwargs):
        tenant_id = self.request.user.tenant_id
        all_routers = api.neutron.router_list(request, tenant_id=tenant_id)
        current_routers = [r for r in all_routers
                           if r['id'] in kwargs['initial']['router_ids']]
        return [(r.id, r.name_or_id) for r in current_routers]

    def get_new_router_ids(self, context):
        # context[router_ids] is router IDs to be kept.
        return context['router_ids']

    def handle(self, request, context):
        firewall_id = self.initial['id']
        firewall_name_or_id = self.initial['name'] or firewall_id
        try:
            body = {'router_ids': self.get_new_router_ids(context)}
            firewall = api_fwaas.firewall_update(request, firewall_id, **body)
            msg = (_('Router(s)  was successfully removed from firewall '
                     '%(firewall)s.') %
                   {'firewall': firewall_name_or_id})
            messages.success(request, msg)
            return firewall
        except Exception as e:
            LOG.error('Failed to remove router(s) from firewall %(id)s: '
                      '%(reason)s', {'id': firewall_id, 'reason': e})
            msg = (_('Failed to remove router(s) from firewall %(name)s: '
                     '%(reason)s') %
                   {'name': firewall_name_or_id, 'reason': e})
            redirect = reverse(self.failure_url)
            exceptions.handle(request, msg, redirect=redirect)
