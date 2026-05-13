export namespace api {
	
	export class HealthSnapshot {
	    appVersion: string;
	    uptime: number;
	
	    static createFrom(source: any = {}) {
	        return new HealthSnapshot(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.appVersion = source["appVersion"];
	        this.uptime = source["uptime"];
	    }
	}

}

