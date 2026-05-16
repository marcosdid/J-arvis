package core

import (
	"errors"
	"reflect"
	"testing"
)

func TestTopoSort_NoDeps_StableOrder(t *testing.T) {
	services := map[string]ServiceSpec{
		"a": {Image: "x"},
		"b": {Image: "y"},
	}
	got, err := topoSort(services)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"a", "b"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got=%v, want %v", got, want)
	}
}

func TestTopoSort_DependencyChain(t *testing.T) {
	services := map[string]ServiceSpec{
		"frontend": {Image: "f", DependsOn: []string{"backend"}},
		"backend":  {Image: "b", DependsOn: []string{"db"}},
		"db":       {Image: "d"},
	}
	got, err := topoSort(services)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"db", "backend", "frontend"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got=%v, want %v", got, want)
	}
}

func TestTopoSort_Cycle_ReturnsError(t *testing.T) {
	services := map[string]ServiceSpec{
		"a": {Image: "x", DependsOn: []string{"b"}},
		"b": {Image: "y", DependsOn: []string{"a"}},
	}
	_, err := topoSort(services)
	if !errors.Is(err, ErrCircularDeps) {
		t.Errorf("err=%v, want ErrCircularDeps", err)
	}
}
