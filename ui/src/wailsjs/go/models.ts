export namespace api {
	
	export class CreateTaskInput {
	    project_id: string;
	    title: string;
	    description: string;
	    branch?: string;
	    template?: string;
	
	    static createFrom(source: any = {}) {
	        return new CreateTaskInput(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.project_id = source["project_id"];
	        this.title = source["title"];
	        this.description = source["description"];
	        this.branch = source["branch"];
	        this.template = source["template"];
	    }
	}
	export class HealthSnapshot {
	    appVersion: string;
	    uptime: number;
	    sandbox_available: boolean;
	    sandbox_reason: string;
	
	    static createFrom(source: any = {}) {
	        return new HealthSnapshot(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.appVersion = source["appVersion"];
	        this.uptime = source["uptime"];
	        this.sandbox_available = source["sandbox_available"];
	        this.sandbox_reason = source["sandbox_reason"];
	    }
	}
	export class MasterStatus {
	    running: boolean;
	    pid: number;
	
	    static createFrom(source: any = {}) {
	        return new MasterStatus(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.running = source["running"];
	        this.pid = source["pid"];
	    }
	}
	export class PatchTaskInput {
	    title?: string;
	    description?: string;
	    state?: string;
	    branch?: string;
	
	    static createFrom(source: any = {}) {
	        return new PatchTaskInput(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.title = source["title"];
	        this.description = source["description"];
	        this.state = source["state"];
	        this.branch = source["branch"];
	    }
	}
	export class WorktreeRead {
	    id: string;
	    repository_id: string;
	    repository_name: string;
	    task_id?: string;
	    path: string;
	    branch?: string;
	    is_orphan: boolean;
	
	    static createFrom(source: any = {}) {
	        return new WorktreeRead(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.repository_id = source["repository_id"];
	        this.repository_name = source["repository_name"];
	        this.task_id = source["task_id"];
	        this.path = source["path"];
	        this.branch = source["branch"];
	        this.is_orphan = source["is_orphan"];
	    }
	}

}

export namespace core {
	
	export class CreateProjectInput {
	    name: string;
	    path: string;
	
	    static createFrom(source: any = {}) {
	        return new CreateProjectInput(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.name = source["name"];
	        this.path = source["path"];
	    }
	}

}

export namespace sandbox {
	
	export class TranscriptMessage {
	    role: string;
	    content: string;
	    tool_name?: string;
	    // Go type: time
	    timestamp: any;
	    source_file: string;
	
	    static createFrom(source: any = {}) {
	        return new TranscriptMessage(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.role = source["role"];
	        this.content = source["content"];
	        this.tool_name = source["tool_name"];
	        this.timestamp = this.convertValues(source["timestamp"], null);
	        this.source_file = source["source_file"];
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}

}

export namespace store {
	
	export class Repository {
	    id: string;
	    name: string;
	    sub_path: string;
	
	    static createFrom(source: any = {}) {
	        return new Repository(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.name = source["name"];
	        this.sub_path = source["sub_path"];
	    }
	}
	export class Project {
	    id: string;
	    name: string;
	    path: string;
	    // Go type: time
	    created_at: any;
	    repositories: Repository[];
	
	    static createFrom(source: any = {}) {
	        return new Project(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.name = source["name"];
	        this.path = source["path"];
	        this.created_at = this.convertValues(source["created_at"], null);
	        this.repositories = this.convertValues(source["repositories"], Repository);
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}
	
	export class Session {
	    id: string;
	    task_id: string;
	    status: string;
	    pid?: number;
	    cwd: string;
	    // Go type: time
	    last_hook_at?: any;
	    // Go type: time
	    started_at: any;
	    // Go type: time
	    ended_at?: any;
	
	    static createFrom(source: any = {}) {
	        return new Session(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.task_id = source["task_id"];
	        this.status = source["status"];
	        this.pid = source["pid"];
	        this.cwd = source["cwd"];
	        this.last_hook_at = this.convertValues(source["last_hook_at"], null);
	        this.started_at = this.convertValues(source["started_at"], null);
	        this.ended_at = this.convertValues(source["ended_at"], null);
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}
	export class Task {
	    id: string;
	    project_id: string;
	    title: string;
	    description: string;
	    state: string;
	    branch?: string;
	    template?: string;
	    permission_profile?: string;
	    // Go type: time
	    created_at: any;
	    // Go type: time
	    updated_at: any;
	    active_session_id?: string;
	
	    static createFrom(source: any = {}) {
	        return new Task(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.project_id = source["project_id"];
	        this.title = source["title"];
	        this.description = source["description"];
	        this.state = source["state"];
	        this.branch = source["branch"];
	        this.template = source["template"];
	        this.permission_profile = source["permission_profile"];
	        this.created_at = this.convertValues(source["created_at"], null);
	        this.updated_at = this.convertValues(source["updated_at"], null);
	        this.active_session_id = source["active_session_id"];
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}

}

