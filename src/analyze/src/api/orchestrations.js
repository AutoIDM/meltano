import axios from 'axios';
import utils from '@/utils/utils';

export default {
  index() {
    return axios.get(utils.apiUrl('orchestrations'));
  },

  addExtractors(extractor) {
    return axios.post(utils.apiUrl('orchestrations', 'add-extractor'), extractor);
  },

  addLoaders(loader) {
    return axios.post(utils.apiUrl('orchestrations', 'add-loader'), loader);
  },

  extract(extractor) {
    return axios.post(utils.apiUrl('orchestrations', `extract/${extractor}`));
  },

  selectEntities(extractorEntities) {
    return axios.post(utils.apiUrl('orchestrations', 'select-entities'), extractorEntities);
  },

  installedPlugins() {
    return axios.get(utils.apiUrl('orchestrations', 'installed-plugins'));
  },

  getExtractorEntities(extractor) {
    return axios.post(utils.apiUrl('orchestrations', `entities/${extractor}`));
  },

  getExtractorSettings(extractor) {
    return axios.post(utils.apiUrl('orchestrations', `settings/${extractor}`));
  },

  load(extractor, loader) {
    return axios.post(utils.apiUrl('orchestrations', `load/${loader}`), {
      extractor,
    });
  },

  transform(model, connectionName) {
    return axios.post(utils.apiUrl('orchestrations', `transform/${model}`), {
      connection_name: connectionName,
    });
  },

  connectionNames() {
    return axios.get(utils.apiUrl('orchestrations', 'connection_names'));
  },

  run(payload) {
    return axios.post(utils.apiUrl('orchestrations', 'run'), payload);
  },
};
