<template>
  <div>
    <transition appear enter-active-class="animated fadeIn">
      <q-table
        class="my-sticky-header-table shadow-24"
        :data="table_list"
        row-key="id"
        :separator="separator"
        :loading="loading"
        :filter="filter"
        :columns="columns"
        hide-bottom
        :pagination.sync="pagination"
        no-data-label="No data"
        no-results-label="No data you want"
        :table-style="{ height: height }"
        flat
        bordered
      >
        <template v-slot:top>
          <q-btn-group push>
            <q-btn :label="$t('refresh')" icon="refresh" @click="reFresh()" />
          </q-btn-group>
          <q-space />
          <q-input outlined rounded dense debounce="300" color="primary" v-model="filter" :placeholder="$t('search')" @input="getSearchList()" @keyup.enter="getSearchList()">
            <template v-slot:append>
              <q-icon name="search" @click="getSearchList()"/>
            </template>
          </q-input>
        </template>
        <template v-slot:body="props">
          <q-tr :props="props">
            <q-td key="asn_code" :props="props">{{ props.row.asn_code }}</q-td>
            <q-td key="pallet_count" :props="props">{{ props.row.pallet_count }}</q-td>
            <q-td key="customer_name" :props="props">{{ props.row.supplier }}</q-td>
            <q-td key="creater" :props="props">{{ props.row.creater }}</q-td>
            <q-td key="create_time" :props="props">{{ props.row.create_time }}</q-td>
          </q-tr>
        </template>
      </q-table>
    </transition>
    <template>
      <div v-show="max !== 0" class="q-pa-lg flex flex-center">
        <div>{{ total }} </div>
        <q-pagination
          v-model="current"
          color="black"
          :max="max"
          :max-pages="6"
          boundary-links
          @click="getList()"
        />
        <div>
          <input
            v-model="paginationIpt"
            @blur="changePageEnter"
            @keyup.enter="changePageEnter"
            style="width: 60px; text-align: center"
          />
        </div>
      </div>
      <div v-show="max === 0" class="q-pa-lg flex flex-center">
        <q-btn flat push color="dark" :label="$t('no_data')"></q-btn>
      </div>
    </template>
  </div>
  </template>

<script>
import { getauth } from 'boot/axios_request'
export default {
  name: 'PagePalletStatsInbound',
  data () {
    return {
      openid: '',
      login_name: '',
      authin: '0',
      pathname: 'asn/list/?ordering=-id',
      pathname_previous: '',
      pathname_next: '',
      separator: 'cell',
      loading: false,
      height: '',
      filter: '',
      table_list: [],
      pagination: { page: 1, rowsPerPage: '30' },
      current: 1,
      max: 0,
      total: 0,
      paginationIpt: 1,
      columns: [
        { name: 'asn_code', required: true, label: this.$t('inbound.view_asn.asn_code'), align: 'left', field: 'asn_code' },
        { name: 'pallet_count', label: '库板数', align: 'center', field: 'pallet_count' },
        { name: 'customer_name', label: this.$t('baseinfo.view_customer.customer_name'), align: 'center', field: 'supplier' },
        { name: 'creater', label: this.$t('creater'), align: 'center', field: 'creater' },
        { name: 'create_time', label: this.$t('createtime'), align: 'center', field: 'create_time' }
      ]
    }
  },
  methods: {
    reFresh () { this.getList() },
    getList () {
      var _this = this
      if (_this.$q.localStorage.has('auth')) {
        getauth(_this.pathname + '&page=' + '' + _this.current).then(res => {
          _this.table_list = res.results
          _this.total = res.count
          if (res.count === 0) {
            _this.max = 0
          } else {
            if (Math.ceil(res.count / 30) === 1) {
              _this.max = 0
            } else {
              _this.max = Math.ceil(res.count / 30)
            }
          }
          _this.pathname_previous = res.previous
          _this.pathname_next = res.next
        }).catch(err => {
          _this.$q.notify({
            message: err.detail,
            icon: 'close',
            color: 'negative'
          })
        })
      }
    },
    changePageEnter (e) {
      if (Number(this.paginationIpt) < 1) {
        this.current = 1
        this.paginationIpt = 1
      } else if (Number(this.paginationIpt) > this.max) {
        this.current = this.max
        this.paginationIpt = this.max
      } else {
        this.current = Number(this.paginationIpt)
      }
      this.getList()
    },
    getSearchList () {
      var _this = this
      if (_this.$q.localStorage.has('auth')) {
        _this.current = 1
        _this.paginationIpt = 1
        getauth(_this.pathname + '&asn_code__icontains=' + _this.filter + '&page=' + '' + _this.current).then(res => {
          _this.table_list = res.results
          _this.total = res.count
          if (res.count === 0) {
            _this.max = 0
          } else {
            if (Math.ceil(res.count / 30) === 1) {
              _this.max = 0
            } else {
              _this.max = Math.ceil(res.count / 30)
            }
          }
          _this.pathname_previous = res.previous
          _this.pathname_next = res.next
        }).catch(err => {
          _this.$q.notify({
            message: err.detail,
            icon: 'close',
            color: 'negative'
          })
        })
      }
    },
    getListPrevious () {
      var _this = this
      if (_this.$q.localStorage.has('auth')) {
        getauth(_this.pathname_previous).then(res => {
          _this.table_list = res.results
          _this.pathname_previous = res.previous
          _this.pathname_next = res.next
        }).catch(err => {
          _this.$q.notify({
            message: err.detail,
            icon: 'close',
            color: 'negative'
          })
        })
      }
    },
    getListNext () {
      var _this = this
      if (_this.$q.localStorage.has('auth')) {
        getauth(_this.pathname_next).then(res => {
          _this.table_list = res.results
          _this.pathname_previous = res.previous
          _this.pathname_next = res.next
        }).catch(err => {
          _this.$q.notify({
            message: err.detail,
            icon: 'close',
            color: 'negative'
          })
        })
      }
    }
  },
  created () {
    var _this = this
    if (_this.$q.localStorage.has('openid')) {
      _this.openid = _this.$q.localStorage.getItem('openid')
    } else {
      _this.openid = ''
      _this.$q.localStorage.set('openid', '')
    }
    if (_this.$q.localStorage.has('login_name')) {
      _this.login_name = _this.$q.localStorage.getItem('login_name')
    } else {
      _this.login_name = ''
      _this.$q.localStorage.set('login_name', '')
    }
    if (_this.$q.localStorage.has('auth')) {
      _this.authin = '1'
      _this.getList()
    } else {
      _this.authin = '0'
    }
  },
  mounted () {
    var _this = this
    if (_this.$q.platform.is.electron) {
      _this.height = String(_this.$q.screen.height - 290) + 'px'
    } else {
      _this.height = _this.$q.screen.height - 290 + '' + 'px'
    }
  }
}
</script>

<style>
</style>
