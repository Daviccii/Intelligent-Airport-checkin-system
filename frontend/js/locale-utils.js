(function(global){
  async function loadJSON(url){
    try{ const res = await fetch(url); if(!res.ok) throw new Error(res.statusText); return await res.json(); }catch(e){ console.warn('Failed to load', url, e); return null; }
  }

  const LocaleUtils = {
    currencies: null,
    countryMap: null,
    async init(){
      if(!this.currencies) this.currencies = await loadJSON('/data/currencies-iso4217.json');
      if(!this.countryMap) this.countryMap = await loadJSON('/data/country_currency_payment.json');
    },
    getCurrencyForCountryCode(cc){
      if(!this.countryMap) return null;
      const entry = this.countryMap[cc];
      if(entry && entry.currency) return { code: entry.currency, symbol: entry.currencySymbol || '' };
      if(this.countryMap['default']) return { code: this.countryMap['default'].currency, symbol: this.countryMap['default'].currencySymbol };
      return { code: 'USD', symbol: '$' };
    },
    getPaymentMethodsForCountryCode(cc){
      if(!this.countryMap) return ['card'];
      const entry = this.countryMap[cc];
      if(entry && Array.isArray(entry.paymentMethods)) return entry.paymentMethods;
      if(this.countryMap['default'] && Array.isArray(this.countryMap['default'].paymentMethods)) return this.countryMap['default'].paymentMethods;
      return ['card'];
    },
    formatCurrency(value, currencyCode){
      try{
        return new Intl.NumberFormat(undefined, { style:'currency', currency: currencyCode || 'USD' }).format(Number(value));
      }catch(e){ return (currencyCode?currencyCode+" ":"") + value; }
    }
  };

  global.LocaleUtils = LocaleUtils;
})(window);
